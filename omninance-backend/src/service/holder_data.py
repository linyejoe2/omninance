"""
holder_data.py — Holder-concentration refresh, ported from
omninance-chip-tracker/src/service/holder_data.py (CSV persistence replaced by
the MongoDB holders collection).

TDCC publishes 股權分散表 data weekly — 資料日期 falls on Friday. The refresh:
  1. Short-circuits without any network call when every tracked symbol already
     has data covering the most recent Friday, so the hourly ofelia trigger is
     a cheap no-op most of the time.
  2. Otherwise scrapes norway.twsthr.info for the newest published 資料日期.
  3. If new data exists, downloads the TDCC all-market snapshot once and
     upserts one summary row per stale symbol.
  4. Symbols with no holder history at all get their full history scraped
     (rate-limited to one twsthr.info request per 10 s).
"""
import asyncio
import logging
import time
from datetime import timedelta
from io import StringIO

import pandas as pd
import requests
from pymongo import UpdateOne

from src.core.date_time_util import get_date_tw
from src.models import db as mongo_db
from src.models.Holder import HolderSummaryModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiting — 10 s minimum between any request to norway.twsthr.info
# ---------------------------------------------------------------------------

_last_twsthr_request: float = 0.0
_TWSTHR_INTERVAL: int = 10


def _throttle():
    global _last_twsthr_request
    wait = _TWSTHR_INTERVAL - (time.time() - _last_twsthr_request)
    if wait > 0:
        time.sleep(wait)
    _last_twsthr_request = time.time()


# ---------------------------------------------------------------------------
# Core scrapers (ported from chip-tracker)
# ---------------------------------------------------------------------------

def sync_stock_holder_data(symbol) -> pd.DataFrame:
    """
    抓取股權分配表
    symbol 格式: 2330.TW -> 需轉為 2330
    """
    stock_code = symbol.split('.')[0]
    url = f"https://norway.twsthr.info/StockHolders.aspx?stock={stock_code}"

    try:
        # 該網站有基本的防爬蟲，需加上 Header
        _throttle()
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'

        # 解析表格
        dfs = pd.read_html(StringIO(response.text))
        df = dfs[9]
        df = df.iloc[:-2, 2:15].dropna(how='all')
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

        if df is None:
            return pd.DataFrame()

        return df

    except Exception as e:
        logger.warning(f"[Holder] Error fetching holder data for {symbol}: {e}")
        return pd.DataFrame()


def check_newest_date(symbol: str) -> str | None:
    """
    Returns the newest 資料日期 (YYYYMMDD string) currently published on
    twsthr.info. Result is cached by the caller across symbols to avoid
    repeated requests.
    """
    df = sync_stock_holder_data(symbol)
    if df is None or df.empty:
        return None
    return str(df["資料日期"].iloc[0])


def get_newest_stock_holder_data() -> pd.DataFrame:
    """
    Downloads the TDCC all-market 股權分散表 snapshot (about 10 s — it contains
    every Taiwan stock). Returned in-memory instead of the chip-tracker's
    one-day parquet cache; one download covers every symbol in a refresh run.
    """
    url = 'https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    data = pd.read_csv(url, storage_options=headers)

    data['證券代號'] = data['證券代號'].astype(str).str.strip()

    return data


def get_stock_large_holder_percentage(symbol: str, snapshot: pd.DataFrame) -> pd.Series | None:
    """
    Returns the summary row for *symbol* from the all-market snapshot as a
    Series (without the 'symbol' key), or None if the symbol is absent.
    """
    stock_code = symbol.split('.')[0]
    try:
        match = snapshot[snapshot["證券代號"] == stock_code]
        if match.empty:
            return None
        return _summarize(match)
    except Exception as e:
        logger.warning(f"[Holder] Error summarizing snapshot for {symbol}: {e}")
        return None


def _summarize(df):
    # 第1級至第15級，係持股為1-999 、1,000-5,000、5,001-10,000、10,001-15,000、15,001-20,000、
    # 20,001-30,000、30,001-40,000、40,001-50,000、50,001-100,000、100,001-200,000、
    # 200,001-400,000、400,001-600,000、600,001-800,000、800,001-1,000,000、1,000,001以上等15個級距。
    date = df['資料日期'].iloc[0]

    # 2. 定義「大股東」範圍 (12-15 級對應 400張以上至 1000張以上)
    up400_holder_mask = df['持股分級'].between(12, 15)

    # 3. 定義「總計行」(第 17 級)
    total_row = df[df['持股分級'] == 17].iloc[0]

    # 4. 計算大股東統計量
    up400_holders = df[up400_holder_mask]
    up400_shares = up400_holders['股數'].sum()
    up400_pct = up400_holders['占集保庫存數比例%'].sum()
    up400_count = up400_holders['人數'].sum()

    # 5. 提取總計資訊
    total_shares = total_row['股數']
    total_people = total_row['人數']

    # 6. 封裝結果 (1張 = 1000股)
    summary = {
        "資料日期": date,
        "集保總張數": int((total_shares / 1000).round(0)),
        "總股東 人數": total_people,
        "平均張數/人": ((total_shares / 1000) / total_people if total_people > 0 else 0).round(2),
        ">400張大股東 持有張數": int((up400_shares / 1000).round(0)),
        ">400張大股東 持有百分比": up400_pct,
        ">400張大股東 人數": up400_count,
        "400~600張人數": df.iloc[11]['人數'],
        "600~800張人數": df.iloc[12]['人數'],
        "800~1000張人數": df.iloc[13]['人數'],
        ">1000張人數": df.iloc[14]['人數'],
        ">1000張大股東 持有百分比": df.iloc[14]['占集保庫存數比例%'],
        "收盤價": "0"
    }

    return pd.Series(summary)


# ---------------------------------------------------------------------------
# Chinese column -> HolderSummaryModel field mapping (same as the migration)
# ---------------------------------------------------------------------------

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


def _row_to_doc(symbol: str, rec: dict) -> dict:
    """Chinese-keyed row (scrape or snapshot summary) -> holders document."""
    fields = {HOLDER_COLUMN_MAP[k]: v for k, v in rec.items() if k in HOLDER_COLUMN_MAP}
    for key in HOLDER_INT_FIELDS:
        fields[key] = int(float(fields[key]))
    fields["date"] = str(fields["date"])
    model = HolderSummaryModel(symbol=symbol, **fields)
    return model.model_dump(exclude={"id"})


# ---------------------------------------------------------------------------
# MongoDB refresh orchestration
# ---------------------------------------------------------------------------

def _last_friday_str() -> str:
    """YYYYMMDD of the most recent Friday (Taiwan time, today if Friday)."""
    today = get_date_tw()
    return (today - timedelta(days=(today.weekday() - 4) % 7)).strftime("%Y%m%d")


async def refresh_holders() -> dict:
    """Bring the holders collection up to the newest published TDCC data."""
    db = mongo_db.get_db()

    stock_docs = await db["stock_list"].find({}, {"symbol": 1}).to_list(length=None)
    symbols = [doc["symbol"] for doc in stock_docs]
    if not symbols:
        return {"status": "no_symbols", "total": 0}

    cursor = db["holders"].aggregate(
        [{"$group": {"_id": "$symbol", "last_date": {"$max": "$date"}}}]
    )
    last_dates = {row["_id"]: row["last_date"] for row in await cursor.to_list(length=None)}

    # TDCC publishes weekly, dated Friday — if everything already covers the
    # most recent Friday there is nothing new to fetch.
    last_friday = _last_friday_str()
    if all(last_dates.get(symbol, "") >= last_friday for symbol in symbols):
        logger.info(f"[Holder] Up to date (>= {last_friday}); skipping refresh")
        return {"status": "up_to_date", "total": len(symbols), "newest_date": last_friday}

    probe_symbol = next((s for s in symbols if s in last_dates), symbols[0])
    newest = await asyncio.to_thread(check_newest_date, probe_symbol)
    if newest is None:
        logger.warning("[Holder] Cannot reach twsthr.info — skipping refresh")
        return {"status": "source_unreachable", "total": len(symbols)}

    updated = 0
    skipped = 0
    full_history: list[str] = []
    failed: list[str] = []
    snapshot: pd.DataFrame | None = None

    for symbol in symbols:
        local_last = last_dates.get(symbol)

        # New symbol — no holder history yet: fetch the full table (throttled)
        if local_last is None:
            df = await asyncio.to_thread(sync_stock_holder_data, symbol)
            if df is None or df.empty:
                failed.append(symbol)
                continue
            try:
                docs = [_row_to_doc(symbol, rec) for rec in df.to_dict(orient="records")]
                ops = [
                    UpdateOne({"symbol": symbol, "date": d["date"]}, {"$set": d}, upsert=True)
                    for d in docs
                ]
                await db["holders"].bulk_write(ops, ordered=False)
                full_history.append(symbol)
                updated += len(docs)
            except Exception as exc:
                logger.warning(f"[Holder] Full-history insert failed for {symbol}: {exc}")
                failed.append(symbol)
            continue

        if local_last >= newest:
            skipped += 1
            continue

        # Stale — pull the latest row from the all-market snapshot
        if snapshot is None:
            logger.info(f"[Holder] Downloading TDCC snapshot ({newest})...")
            snapshot = await asyncio.to_thread(get_newest_stock_holder_data)

        row = get_stock_large_holder_percentage(symbol, snapshot)
        if row is None:
            failed.append(symbol)
            continue
        try:
            doc = _row_to_doc(symbol, row.to_dict())
            await db["holders"].update_one(
                {"symbol": symbol, "date": doc["date"]}, {"$set": doc}, upsert=True
            )
            updated += 1
        except Exception as exc:
            logger.warning(f"[Holder] Upsert failed for {symbol}: {exc}")
            failed.append(symbol)

    summary = {
        "status": "refreshed",
        "total": len(symbols),
        "newest_date": newest,
        "updated": updated,
        "skipped": skipped,
        "full_history": full_history,
        "failed": failed,
    }
    logger.info(f"[Holder] Refresh finished: {summary}")
    return summary
