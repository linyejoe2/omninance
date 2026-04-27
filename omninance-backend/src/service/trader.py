from sqlmodel import Session
from datetime import datetime
import httpx
from src.db import TradeRecord, engine
import logging
import os
from typing import Dict, Optional
from dataclasses import dataclass
from src.core.date_time_util import get_datetime_tw


logger = logging.getLogger(__name__)

_OMNITRADER_URL = os.environ.get("OMNITRADER_URL", "http://omnitrader:8000")

def _to_stock_no(symbol: str) -> str:
    return symbol.split(".")[0]

async def place_buy_order(symbol: str, fund: float, strategy_id: str) -> int | None:
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        # 準備交易紀錄的基礎資料
        record = TradeRecord(
            strategy_id=strategy_id,
            action="BUY",
            symbol=symbol,
            status="PENDING",
            create_at=datetime.now(),
            update_at=datetime.now()
        )

        try:
            payload = {
                "stock_no": _to_stock_no(symbol),
                "tick": 2,
                "fund": fund,
                "user_def": f"omni-{strategy_id[:8]}",
            }
            
            # 呼叫下單 API
            # {
            #     "status": "success",
            #     "order_id": "Z0267",
            #     "executed_price": 23.35,
            #     "quantity": 1282,
            #     "detail": {
            #         "ord_date": "20260424",
            #         "ord_time": "105433196",
            #         "ord_type": "2",
            #         "ord_no": "Z0267",
            #         "ret_code": "000000",
            #         "ret_msg": "",
            #         "work_date": "20260424"
            #     }
            # }
            res = await client.post("/api/orders/aggressive-limit-order", json=payload)
            res_data = res.json()
            
            # 更新紀錄資訊
            record.result = res.text
            if res.status_code == 200:
                record.order_id = res_data.get("order_id")
                # 如果 API 直接回傳成交狀態，可以在此更新，否則維持 PENDING
                logger.info(f"[Order] {symbol} placed successfully: {record.order_id}")
            else:
                record.status = "FAILED"
                record.error = f"API Error: {res.status_code}"
                logger.warning(f"[Order] {symbol} rejected by API: {res.text}")

        except Exception as exc:
            logger.error("[Execute] Order exception for %s: %s", symbol, exc)
            record.status = "FAILED"
            record.error = str(exc)

        # 寫入資料庫
        try:
            with Session(engine) as session:
                session.add(record)
                session.commit()
                session.refresh(record)
                return record.id  # 返回 SQLModel 自動生成的自增 ID
        except Exception as db_exc:
            logger.error("[DB] Failed to save trade record for %s: %s", symbol, db_exc)
            return None
        
async def place_sell_order(symbol: str, quantity: float, strategy_id: str) -> list[int]:
    """
    呼叫 OmniTrader 執行賣出 (清倉或停損)。
    """
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        try:
            # 2. 準備 Payload 
            # 注意：賣出使用的是 quantity (股)
            payload = {
                "stock_no": _to_stock_no(symbol),
                "tick": 2,             # 賣出時 API 會執行 (現價 - 2 ticks) 確保成交
                "quantity": quantity,
                "user_def": f"omni-{strategy_id[:8]}",
            }
            
            # 3. 呼叫賣出 API
            # {
            # "status": "success",
            # "stock_no": "3481",
            # "target_price": 23.1,
            # "total_requested_qty": 1429,
            # "order_details": [
            #     {
            #     "type": "COMMON",
            #     "status": "success",
            #     "order_id": "Z0268",
            #     "qty": 1
            #     },
            #     {
            #     "type": "ODD",
            #     "status": "success",
            #     "order_id": "Z0269",
            #     "qty": 429
            #     }
            # ]
            # }
            res = await client.post("/api/orders/sell-at-best-price", json=payload)
            res.raise_for_status()
            res_data = res.json()
            
            # 取得拆單明細
            order_details = res_data.get("order_details", [])
            created_ids = []
            
            with Session(engine) as session:
                for detail in order_details:
                    # 只有成功的委託才建立紀錄
                    if detail.get("status") == "success":
                        record = TradeRecord(
                            strategy_id=strategy_id,
                            action="SELL",
                            symbol=symbol,
                            order_id=detail.get("order_id"), # 這裡拿的是該筆拆單的單號 (如 Z0267)
                            # 注意：這裡要存入拆分後的數量 (detail['qty']) 而非原始總量
                            quantity=detail.get("qty"), 
                            status="PENDING",
                            result=res.text,
                            create_at=get_datetime_tw(),
                            update_at=get_datetime_tw()
                        )
                        session.add(record)
                        session.flush() # 取得 record.id 但先不 commit
                        created_ids.append(record.id)
                
                session.commit()
            
            if not created_ids:
                logger.error(f"[Order] {symbol} Sell failed: {res.text}")
            
            return created_ids
            
        except Exception as exc:
            logger.error(f"[Execute] Sell exception for {symbol}: {exc}")
            return []
    
@dataclass
class OrderStatus:
    order_id: str
    is_filled: bool
    filled_qty: float
    total_qty: float
    is_failed: bool
    error_msg: Optional[str] = None
    
async def get_all_orders() -> Dict[str, OrderStatus]:
    """抓取所有訂單並標準化格式"""
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        resp = await client.get("/api/orders")
        resp.raise_for_status()
        
        raw_orders = resp.json()
        standardized = {}
        
        for o in raw_orders:
            ord_no = o.get("ord_no")
            if not ord_no: continue
            
            filled = o.get("mat_qty_share", 0)
            total = o.get("org_qty_share", 0)
            err_code = o.get("err_code", "00000000")
            
            standardized[ord_no] = OrderStatus(
                order_id=ord_no,
                is_filled=(total > 0 and filled >= total),
                filled_qty=filled,
                total_qty=total,
                is_failed=(err_code != "00000000"),
                error_msg=o.get("err_msg")
            )
        return standardized
    
async def get_quote(symbol: str) -> float:
    """取得即時報價"""
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        resp = await client.get(f"/api/market/quote/{_to_stock_no(symbol)}")
        resp.raise_for_status()
        return float(resp.text)
    
    
get_quote("2330.TW")