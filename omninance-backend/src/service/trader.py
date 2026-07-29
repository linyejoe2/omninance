"""
trader.py — omnitrader (E.SUN brokerage) client.

Places orders through the omnitrader service and records every request as an
order_record row. Order placement is a hard boundary: the record is committed
in its own transaction so a broker order can never exist without a DB trace,
even if the caller later fails.
"""
import logging
import os
from decimal import Decimal
from typing import Dict, Optional

import httpx
from pydantic import BaseModel

from src.core.decimal_util import to_decimal
from src.db import get_session
from src.models.trading import OrderAction, OrderRecord, OrderStatus, SellReason
from src.repositories import order_record_repo

logger = logging.getLogger(__name__)

_OMNITRADER_URL = os.environ.get("OMNITRADER_URL", "http://omnitrader:8000")


def _to_stock_no(symbol: str) -> str:
    return symbol.split(".")[0]


async def place_buy_order(symbol: str, fund: Decimal, strategy_id: str) -> Optional[int]:
    """Place an aggressive limit buy sized by fund; returns the order_record id."""
    record = OrderRecord(
        strategy_id=strategy_id,
        action=OrderAction.BUY,
        symbol=symbol,
        status=OrderStatus.PENDING,
        req_quantity=0,  # 由券商依 fund 計算，回應後補上
    )

    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        try:
            payload = {
                "stock_no": _to_stock_no(symbol),
                "tick": 2,
                "fund": float(fund),
                "user_def": f"omni-{strategy_id[:8]}",
            }
            res = await client.post("/api/orders/aggressive-limit-order", json=payload)
            res_data = res.json()

            if res.status_code == 200:
                record.broker_order_id = res_data.get("order_id")
                record.req_quantity = int(res_data.get("quantity") or 0)
                if res_data.get("executed_price") is not None:
                    record.req_price = to_decimal(res_data["executed_price"])
                logger.info(f"[Order] BUY {symbol} placed: {record.broker_order_id}")
            else:
                record.status = OrderStatus.FAILED
                record.error_msg = f"API Error {res.status_code}: {res.text[:500]}"
                logger.warning(f"[Order] BUY {symbol} rejected: {res.text}")

        except Exception as exc:
            logger.error(f"[Order] BUY exception for {symbol}: {exc}")
            record.status = OrderStatus.FAILED
            record.error_msg = str(exc)

    async with get_session() as session:
        await order_record_repo.create_order(session, record)
        await session.commit()
        return record.id


async def place_sell_order(
    symbol: str,
    quantity: int,
    strategy_id: str,
    sell_reason: SellReason = SellReason.TRAILING_STOP,
) -> list[int]:
    """Sell at best price (現價 - 2 ticks). The broker may split into common +
    odd-lot orders; one order_record per split. Returns the created ids."""
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        try:
            payload = {
                "stock_no": _to_stock_no(symbol),
                "tick": 2,
                "quantity": quantity,
                "user_def": f"omni-{strategy_id[:8]}",
            }
            res = await client.post("/api/orders/sell-at-best-price", json=payload)
            res.raise_for_status()
            res_data = res.json()

            target_price = res_data.get("target_price")
            order_details = res_data.get("order_details", [])
            created_ids: list[int] = []

            async with get_session() as session:
                for detail in order_details:
                    if detail.get("status") != "success":
                        continue
                    record = OrderRecord(
                        strategy_id=strategy_id,
                        action=OrderAction.SELL,
                        sell_reason=sell_reason,
                        symbol=symbol,
                        broker_order_id=detail.get("order_id"),
                        req_quantity=int(detail.get("qty") or 0),
                        req_price=to_decimal(target_price) if target_price is not None else None,
                        status=OrderStatus.PENDING,
                    )
                    await order_record_repo.create_order(session, record)
                    created_ids.append(record.id)
                await session.commit()

            if not created_ids:
                logger.error(f"[Order] SELL {symbol} produced no orders: {res.text}")
            return created_ids

        except Exception as exc:
            logger.error(f"[Order] SELL exception for {symbol}: {exc}")
            return []


class BrokerOrderStatus(BaseModel):
    order_id: str
    is_filled: bool
    filled_qty: int
    total_qty: int
    avg_price: Decimal = Decimal("0")
    is_failed: bool
    error_msg: Optional[str] = None


async def get_all_orders() -> Dict[str, BrokerOrderStatus]:
    """Fetch today's broker orders keyed by 委託書號."""
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        resp = await client.get("/api/orders")
        resp.raise_for_status()

        standardized: Dict[str, BrokerOrderStatus] = {}
        for o in resp.json():
            ord_no = o.get("ord_no")
            if not ord_no:
                continue

            filled = int(o.get("mat_qty_share", 0))
            total = int(o.get("org_qty_share", 0))
            err_code = o.get("err_code", "00000000")

            standardized[ord_no] = BrokerOrderStatus(
                order_id=ord_no,
                is_filled=(total > 0 and filled >= total),
                filled_qty=filled,
                total_qty=total,
                avg_price=to_decimal(o.get("avg_price", 0)),
                is_failed=(err_code != "00000000"),
                error_msg=o.get("err_msg"),
            )
        return standardized


async def get_quote(symbol: str) -> Optional[Decimal]:
    """即時報價；失敗回傳 None，呼叫端必須自行處理缺值。"""
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        try:
            resp = await client.get(f"/api/market/quote/{_to_stock_no(symbol)}")
            resp.raise_for_status()
            return to_decimal(resp.text)
        except Exception as exc:
            logger.warning(f"[Quote] Failed for {symbol}: {exc}")
            return None
