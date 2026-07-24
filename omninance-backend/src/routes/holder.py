"""
holder.py — Holder data maintenance endpoints.

  POST /api/holders/refresh — bring the holders collection up to the newest
                              published TDCC 股權分散表 data (called hourly by
                              the ofelia scheduler; the source publishes new
                              data weekly, dated Friday)
"""
from fastapi import APIRouter

from src.service.holder_data import refresh_holders

router = APIRouter(tags=["holders"])


@router.post("/api/holders/refresh")
async def refresh():
    return await refresh_holders()
