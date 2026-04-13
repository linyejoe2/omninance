"""
strategy.py — Strategy execution orchestration.

  POST /api/strategy/start       — buy signals via omnitrader; record in SQLite
  POST /api/strategy/stop        — sell held positions via omnitrader; record in SQLite
  GET  /api/strategy/executions  — execution history from SQLite
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import insert_execution, list_executions

router = APIRouter(prefix="/api/strategy", tags=["strategy"])
logger = logging.getLogger(__name__)

_SIGNALS_PATH = Path(os.environ.get("SIGNALS_PATH", "/app/signals/latest_signals.json"))
_OMNITRADER_URL = os.environ.get("OMNITRADER_URL", "http://omnitrader:8000")


def _load_signals() -> dict:
    if not _SIGNALS_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Signal file not found: {_SIGNALS_PATH}")
    return json.loads(_SIGNALS_PATH.read_text(encoding="utf-8"))


def _parse_signals(raw: dict) -> tuple[list[str], list[str], dict]:
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
    """'2330.TW' → '2330'"""
    return symbol.split(".")[0]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StartRequest(BaseModel):
    initial_capital: float = 100000.0


@router.post("/start")
def start_strategy(req: StartRequest):
    """
    Execute buy signals from the latest signal file.

    Calculates lots per stock from initial_capital, places market buy orders
    via omnitrader, and persists each result in SQLite.
    """
    raw = _load_signals()
    buy_list, _, snapshot = _parse_signals(raw)

    if not buy_list:
        return {"buy": [], "errors": [], "message": "No buy signals"}

    avg_price = (
        sum(snapshot.get(s, {}).get("p", 0) for s in buy_list) / len(buy_list)
        if buy_list else 0
    )
    lots = (
        max(1, int(req.initial_capital / len(buy_list) / (avg_price * 1000)))
        if avg_price > 0 else 1
    )

    results: dict = {"buy": [], "errors": []}

    with httpx.Client(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        for symbol in buy_list:
            stock_no = _to_stock_no(symbol)
            price = snapshot.get(symbol, {}).get("p")
            try:
                res = client.post("/api/orders", json={
                    "stock_no": stock_no,
                    "buy_sell": "B",
                    "quantity": lots,
                    "price_flag": "4",   # market order
                    "price": None,
                    "user_def": "omninance-backend",
                })
                insert_execution("start", symbol, lots, price, res.text, None, _now_iso())
                results["buy"].append({"symbol": symbol, "result": res.json()})
                logger.info("[Start] BUY %s qty=%d", symbol, lots)
            except Exception as exc:
                insert_execution("start", symbol, lots, price, None, str(exc), _now_iso())
                results["errors"].append({"symbol": symbol, "error": str(exc)})
                logger.error("[Start] BUY %s failed: %s", symbol, exc)

    return results


@router.post("/stop")
def stop_strategy():
    """
    Exit all buy-list positions at market price.

    Fetches current inventory from omnitrader and only sells symbols
    that are actually held. Persists each result in SQLite.
    """
    raw = _load_signals()
    buy_list, _, _ = _parse_signals(raw)

    with httpx.Client(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        try:
            inv_res = client.get("/api/account/inventories")
            inventories = inv_res.json() if inv_res.is_success else []
        except Exception as exc:
            logger.warning("Could not fetch inventories: %s", exc)
            inventories = []

    held_stocks = {inv["stock_no"] for inv in inventories if isinstance(inv, dict)}

    results: dict = {"sell": [], "skipped": [], "errors": []}

    with httpx.Client(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        for symbol in buy_list:
            stock_no = _to_stock_no(symbol)
            if stock_no not in held_stocks:
                results["skipped"].append({"symbol": symbol, "reason": "not in inventory"})
                logger.info("[Stop] %s skipped — not held", symbol)
                continue
            try:
                res = client.post("/api/orders", json={
                    "stock_no": stock_no,
                    "buy_sell": "S",
                    "quantity": 1,
                    "price_flag": "4",
                    "price": None,
                    "user_def": "omninance-backend-stop",
                })
                insert_execution("stop", symbol, 1, None, res.text, None, _now_iso())
                results["sell"].append({"symbol": symbol, "result": res.json()})
                logger.info("[Stop] SELL %s", symbol)
            except Exception as exc:
                insert_execution("stop", symbol, 1, None, None, str(exc), _now_iso())
                results["errors"].append({"symbol": symbol, "error": str(exc)})
                logger.error("[Stop] SELL %s failed: %s", symbol, exc)

    return results


@router.get("/executions")
def get_executions(limit: int = 100):
    """Return the most recent execution records from SQLite."""
    return list_executions(limit)
