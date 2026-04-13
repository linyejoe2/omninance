"""
price_history.py — Serve price history from the chip-tracker price matrix.

Reads price_matrix.parquet from MATRIX_PATH (env, default /app/matrix).
Returns normalized or raw daily close prices for the requested symbols.
"""
import logging
import os
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/price-history", tags=["price-history"])
logger = logging.getLogger(__name__)

_MATRIX_DIR = Path(os.environ.get("MATRIX_PATH", "/app/matrix"))


@router.get("")
def get_price_history(
    symbols: str = Query(..., description="Comma-separated symbol list, e.g. '2330.TW,6488.TWO'"),
    days: int = Query(30, ge=1, le=365, description="Number of recent trading days to return"),
):
    """
    Return daily close prices for the given symbols over the last `days` trading days.

    Response: list of { date: str, <symbol>: float | null, ... }
    """
    parquet_path = _MATRIX_DIR / "price_matrix.parquet"
    if not parquet_path.exists():
        raise HTTPException(status_code=404, detail=f"price_matrix.parquet not found at {_MATRIX_DIR}")

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as exc:
        logger.error("Failed to read price_matrix.parquet: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read price matrix")

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    available = [s for s in symbol_list if s in df.columns]

    if not available:
        raise HTTPException(status_code=404, detail=f"None of the requested symbols found in price matrix. Available sample: {list(df.columns[:5])}")

    df = df[available].tail(days).dropna(how="all")

    result = []
    for date, row in df.iterrows():
        entry: dict = {"date": str(date.date()) if hasattr(date, "date") else str(date)}
        for sym in available:
            val = row.get(sym)
            entry[sym] = round(float(val), 2) if pd.notna(val) else None
        result.append(entry)

    return result
