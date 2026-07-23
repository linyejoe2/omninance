"""
stock_list.py — StockList maintenance endpoints.

  POST /api/stock-list/refresh — refresh stale stock_list entries via yfinance
                                 (called hourly by the ofelia scheduler)
"""
from fastapi import APIRouter, Query

from src.service.stock_list import DEFAULT_MAX_AGE_HOURS, refresh_stock_list

router = APIRouter(tags=["stock-list"])


@router.post("/api/stock-list/refresh")
async def refresh(max_age_hours: int = Query(default=DEFAULT_MAX_AGE_HOURS, ge=0)):
    """Refresh symbols whose updated_at is older than max_age_hours (default 12 → twice a day)."""
    return await refresh_stock_list(max_age_hours)
