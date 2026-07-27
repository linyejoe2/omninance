"""
ticker.py — Ticker (OHLCV) maintenance endpoints.

  POST /api/tickers/refresh — bring the tickers collection up to the newest
                              expected trading day via yfinance (called
                              hourly by the ofelia scheduler)
"""
from fastapi import APIRouter

from src.service.schedule_log import run_with_log
from src.service.ticker_data import refresh_tickers

router = APIRouter(tags=["tickers"])


@router.post("/api/tickers/refresh")
async def refresh():
    return await run_with_log("ticker-refresh", refresh_tickers)
