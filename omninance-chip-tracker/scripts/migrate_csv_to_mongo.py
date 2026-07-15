"""
scripts/migrate_csv_to_mongo.py — one-time migration of existing CSV data into MongoDB.

Reads:
  data/raw/tickers/{SYMBOL_KEY}.csv          -> "tickers" collection
  data/raw/holders/{SYMBOL_KEY}_holders.csv  -> "holders" collection

SYMBOL_KEY is the on-disk symbol form (e.g. "2330_TW") and is converted back
to the dotted symbol used elsewhere in the app (e.g. "2330.TW"), matching the
inverse of `symbol.replace(".", "_")` used when the CSVs were written
(see src/main.py::run_phase1).

Rows are upserted keyed on (symbol, date), matching the unique index created
in src/models/db.py, so the script is safe to re-run.

Usage (from omninance-chip-tracker/):
  uv run python scripts/migrate_csv_to_mongo.py [--dry-run]
"""
import argparse
import asyncio
import sys
from pathlib import Path

CHIP_TRACKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CHIP_TRACKER_ROOT))

import pandas as pd
from dotenv import load_dotenv
from pymongo import ReplaceOne, UpdateOne

load_dotenv(CHIP_TRACKER_ROOT.parent / ".env")

from src.models import db
from src.models.Holder import HolderSummaryModel
from src.models.Ticker import TickerModel

RAW_TICKERS_DIR = CHIP_TRACKER_ROOT / "data" / "raw" / "tickers"
RAW_HOLDERS_DIR = CHIP_TRACKER_ROOT / "data" / "raw" / "holders"

# CSV header (utf-8-sig, BOM stripped) -> HolderSummaryModel field name
HOLDER_COLUMN_MAP = {
    "資料日期": "date",
    "集保總張數": "total_sheets",
    "總股東 人數": "total_shareholders",
    "平均張數/人": "avg_sheets_per_person",
    ">400張大股東 持有張數": "over400_sheets",
    ">400張大股東 持有百分比": "over400_percentage",
    ">400張大股東 人數": "over400_count",
    "400~600張人數": "count_400_to_600",
    "600~800張人數": "count_600_to_800",
    "800~1000張人數": "count_800_to_1000",
    ">1000張人數": "over1000_count",
    ">1000張大股東 持有百分比": "over1000_percentage",
    "收盤價": "close_price",
}
HOLDER_INT_FIELDS = {
    "total_sheets", "total_shareholders", "over400_sheets", "over400_count",
    "count_400_to_600", "count_600_to_800", "count_800_to_1000", "over1000_count",
}


def file_key_to_symbol(file_key: str) -> str:
    """'2330_TW' -> '2330.TW', '1785_TWO' -> '1785.TWO'"""
    return file_key.replace("_", ".", 1)


def load_ticker_rows(csv_path: Path, symbol: str) -> list[dict]:
    df = pd.read_csv(csv_path, dtype={"Date": str})
    rows = []
    for rec in df.to_dict(orient="records"):
        model = TickerModel(
            symbol=symbol,
            date=rec["Date"],
            Open=rec["Open"],
            High=rec["High"],
            Low=rec["Low"],
            Close=rec["Close"],
            Volume=int(rec["Volume"]),
        )
        rows.append(model.model_dump(exclude={"id"}))
    return rows


def load_holder_rows(csv_path: Path, symbol: str) -> list[dict]:
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype={"資料日期": str})
    rows = []
    for rec in df.to_dict(orient="records"):
        fields = {HOLDER_COLUMN_MAP[k]: v for k, v in rec.items()}
        for key in HOLDER_INT_FIELDS:
            fields[key] = int(fields[key])
        model = HolderSummaryModel(symbol=symbol, **fields)
        rows.append(model.model_dump(exclude={"id"}))
    return rows


async def upsert_many(collection, rows: list[dict]) -> tuple[int, int]:
    """Upsert on (symbol, date) via $set. Returns (matched, upserted) counts."""
    if not rows:
        return 0, 0
    ops = [
        UpdateOne({"symbol": r["symbol"], "date": r["date"]}, {"$set": r}, upsert=True)
        for r in rows
    ]
    result = await collection.bulk_write(ops, ordered=False)
    return result.matched_count, result.upserted_count


async def replace_many(collection, rows: list[dict]) -> tuple[int, int]:
    """Upsert on (symbol, date) via full document replace (drops stale fields
    from a previous schema). Returns (matched, upserted) counts."""
    if not rows:
        return 0, 0
    ops = [
        ReplaceOne({"symbol": r["symbol"], "date": r["date"]}, r, upsert=True)
        for r in rows
    ]
    result = await collection.bulk_write(ops, ordered=False)
    return result.matched_count, result.upserted_count


async def migrate(kind: str, files: list[Path], to_symbol, to_rows, write, dry_run: bool) -> None:
    print(f"[{kind}] Found {len(files)} CSV file(s)")
    collection = None if dry_run else db.get_db()[kind.lower()]
    total_matched = total_upserted = 0

    for path in sorted(files):
        symbol = to_symbol(path)
        rows = to_rows(path, symbol)
        if dry_run:
            print(f"  [DryRun] {symbol}: {len(rows)} row(s)")
            continue
        matched, upserted = await write(collection, rows)
        total_matched += matched
        total_upserted += upserted
        print(f"  {symbol}: {len(rows)} row(s) -> matched={matched} upserted={upserted}")

    if not dry_run:
        print(f"[{kind}] Done. matched={total_matched} upserted={total_upserted}")


async def main(dry_run: bool) -> None:
    if not dry_run:
        await db.connect()
    try:
        await migrate(
            "Tickers",
            list(RAW_TICKERS_DIR.glob("*.csv")),
            to_symbol=lambda p: file_key_to_symbol(p.stem),
            to_rows=load_ticker_rows,
            write=upsert_many,
            dry_run=dry_run,
        )
        await migrate(
            "Holders",
            list(RAW_HOLDERS_DIR.glob("*_holders.csv")),
            to_symbol=lambda p: file_key_to_symbol(p.name[: -len("_holders.csv")]),
            to_rows=load_holder_rows,
            write=replace_many,
            dry_run=dry_run,
        )
    finally:
        if not dry_run:
            db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-time CSV -> MongoDB migration")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count rows without connecting to MongoDB or writing anything",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
