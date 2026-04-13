"""
signals.py — Read chip-tracker signal file and execute trades.

Expects the signal file written by omninance-chip-tracker at:
  SIGNALS_PATH (env, default /app/signals/latest_signals.json)

Supports both signal formats:
  - New:  { metadata, actions: { buy, sell_hint }, snapshot }
  - Legacy: { action_date, buy_list, sell_list }
"""
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from esun_trade.constant import Action, APCode, BSFlag, PriceFlag, Trade
from esun_trade.order import OrderObject
from src.sdk_client import get_sdk

router = APIRouter(prefix="/api/signals", tags=["signals"])
logger = logging.getLogger(__name__)

_SIGNALS_PATH = Path(os.environ.get("SIGNALS_PATH", "/app/signals/latest_signals.json"))


def _load_signals() -> dict:
    if not _SIGNALS_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Signal file not found: {_SIGNALS_PATH}")
    return json.loads(_SIGNALS_PATH.read_text(encoding="utf-8"))


def _parse_signals(raw: dict) -> tuple[list[str], list[str], dict]:
    """Return (buy_list, sell_list, snapshot) from either signal format."""
    if "actions" in raw:
        buy_list = raw["actions"].get("buy", [])
        sell_list = raw["actions"].get("sell_hint", [])
        snapshot = raw.get("snapshot", {})
    else:
        buy_list = raw.get("buy_list", [])
        sell_list = raw.get("sell_list", [])
        snapshot = {}
    return buy_list, sell_list, snapshot


def _to_stock_no(symbol: str) -> str:
    """'2330.TW' → '2330',  '6488.TWO' → '6488'"""
    return symbol.split(".")[0]


class ExecuteRequest(BaseModel):
    quantity: int = 1
    price_flag: str = PriceFlag.Limit   # "4" for market order
    trade: str = Trade.Cash
    dry_run: bool = False               # preview without placing orders


@router.get("")
def get_signals():
    """Preview the current signal file without executing."""
    return _load_signals()


@router.post("/stop")
def stop_signals():
    """
    Exit all current buy-list positions at market price.

    Sells every symbol in the current buy_list that is also held in inventory.
    Symbols not in inventory are skipped safely.
    """
    sdk = get_sdk()
    raw = _load_signals()
    buy_list, _, _ = _parse_signals(raw)

    inventories = sdk.get_inventories() or []
    held_stocks = {inv["stock_no"] for inv in inventories}

    results: dict = {"sell": [], "skipped": [], "errors": []}

    for symbol in buy_list:
        stock_no = _to_stock_no(symbol)
        if stock_no not in held_stocks:
            results["skipped"].append({"symbol": symbol, "reason": "not in inventory"})
            logger.info("[Stop] %s skipped — not held", symbol)
            continue
        try:
            order = OrderObject(
                buy_sell=Action.Sell,
                price=None,
                stock_no=stock_no,
                quantity=1,
                price_flag=PriceFlag.Market,
                trade=Trade.Cash,
                user_def="omnitrader-stop",
            )
            result = sdk.place_order(order)
            results["sell"].append({"symbol": symbol, "result": result})
            logger.info("[Stop] SELL %s market order placed", symbol)
        except Exception as exc:
            results["errors"].append({"symbol": symbol, "error": str(exc)})
            logger.error("[Stop] SELL %s failed: %s", symbol, exc)

    return results


@router.post("/execute")
def execute_signals(req: ExecuteRequest):
    """
    Execute buy/sell orders based on the latest signal file.

    - buy:  places orders for every symbol in buy_list using snapshot price.
    - sell: only places orders for symbols already in inventory (safe-guard).
    - dry_run=true: returns the planned orders without sending them.
    """
    sdk = get_sdk()
    raw = _load_signals()
    buy_list, sell_list, snapshot = _parse_signals(raw)

    # Resolve current holdings to guard against selling what we don't own
    inventories = sdk.get_inventories() or []
    held_stocks = {inv["stock_no"] for inv in inventories}

    results: dict = {"buy": [], "sell": [], "skipped": [], "errors": []}

    is_limit = PriceFlag(req.price_flag) == PriceFlag.Limit

    # --- BUY ---
    for symbol in buy_list:
        stock_no = _to_stock_no(symbol)
        price = snapshot.get(symbol, {}).get("p", 0.0) if is_limit else None
        try:
            order = OrderObject(
                buy_sell=Action.Buy,
                price=price,
                stock_no=stock_no,
                quantity=req.quantity,
                price_flag=PriceFlag(req.price_flag),
                trade=Trade(req.trade),
                user_def="omnitrader",
            )
            if req.dry_run:
                results["buy"].append({"symbol": symbol, "planned": str(order)})
            else:
                result = sdk.place_order(order)
                results["buy"].append({"symbol": symbol, "result": result})
                logger.info("[Execute] BUY  %s  qty=%d  price=%s", symbol, req.quantity, price)
        except Exception as exc:
            results["errors"].append({"symbol": symbol, "action": "buy", "error": str(exc)})
            logger.error("[Execute] BUY  %s  failed: %s", symbol, exc)

    # --- SELL ---
    for symbol in sell_list:
        stock_no = _to_stock_no(symbol)
        if stock_no not in held_stocks:
            results["skipped"].append({"symbol": symbol, "reason": "not in inventory"})
            logger.info("[Execute] SELL %s  skipped — not held", symbol)
            continue
        price = snapshot.get(symbol, {}).get("p", 0.0) if is_limit else None
        try:
            order = OrderObject(
                buy_sell=Action.Sell,
                price=price,
                stock_no=stock_no,
                quantity=req.quantity,
                price_flag=PriceFlag(req.price_flag),
                trade=Trade(req.trade),
                user_def="omnitrader",
            )
            if req.dry_run:
                results["sell"].append({"symbol": symbol, "planned": str(order)})
            else:
                result = sdk.place_order(order)
                results["sell"].append({"symbol": symbol, "result": result})
                logger.info("[Execute] SELL %s  qty=%d  price=%s", symbol, req.quantity, price)
        except Exception as exc:
            results["errors"].append({"symbol": symbol, "action": "sell", "error": str(exc)})
            logger.error("[Execute] SELL %s  failed: %s", symbol, exc)

    return results
