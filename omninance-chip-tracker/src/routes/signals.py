"""
signals.py — Read-only signal and price-matrix API endpoints.

  GET /api/signals        — latest chip-tracker signal file (dist/latest_signals.json)
  GET /api/price-history  — daily close prices from data/matrix/price_matrix.parquet
"""
import json
import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["signals"])
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent.parent
_SIGNALS_PATH = ROOT / "dist" / "latest_signals.json"
_MATRIX_DIR = ROOT / "data" / "matrix"


@router.get("/api/signals")
def get_signals():
    if not _SIGNALS_PATH.exists():
        raise HTTPException(status_code=404, detail="Signal file not found")
    return json.loads(_SIGNALS_PATH.read_text(encoding="utf-8"))


@router.get("/api/price-history")
def get_price_history(
    symbols: str = Query(..., description="Comma-separated symbol list"),
    days: int = Query(30, ge=1, le=365),
):
    parquet_path = _MATRIX_DIR / "price_matrix.parquet"
    if not parquet_path.exists():
        raise HTTPException(status_code=404, detail="price_matrix.parquet not found — run the pipeline first")

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as exc:
        logger.error("Failed to read price_matrix.parquet: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read price matrix")

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    available = [s for s in symbol_list if s in df.columns]
    if not available:
        raise HTTPException(
            status_code=404,
            detail=f"None of the requested symbols found. Sample: {list(df.columns[:5])}",
        )

    df = df[available].tail(days).dropna(how="all")
    result = []
    for date, row in df.iterrows():
        entry: dict = {"date": str(date.date()) if hasattr(date, "date") else str(date)}
        for sym in available:
            val = row.get(sym)
            entry[sym] = round(float(val), 2) if pd.notna(val) else None
        result.append(entry)
    return result
