"""
db.py — SQLite persistence for strategy management.

Schema:
  strategy(_id, initial_capital, partition, volume_multiplier,
           concentration_slope, atr_multiplier, back_test_period,
           status, create_date)
  strategy_daily_log(_id, strategy_id, run_date, total_equity, daily_pnl,
                     holdings_snapshot, error)  UNIQUE(strategy_id, run_date)
  trade_record(_id, strategy_id, action CHECK('BUY'|'SELL'), symbol,
               quantity, price, pnl, fee, return_rate, result, error, create_date)
"""
import sqlite3
import uuid
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from src.core.date_time_util import get_datetime_tw, get_datetime
from typing import List, Dict, Any

_DB_PATH = Path("/app/database/omninance.db")

def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS strategy (
                _id                 TEXT    PRIMARY KEY,
                initial_capital     REAL    NOT NULL,
                partition           INTEGER NOT NULL,
                volume_multiplier   REAL    NOT NULL,
                concentration_slope REAL    NOT NULL,
                atr_multiplier      REAL    NOT NULL,
                back_test_period    INTEGER NOT NULL,
                status              TEXT    NOT NULL DEFAULT 'active',
                create_at         TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategy_daily_log (
                _id         INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT    NOT NULL,
                run_date    TEXT    NOT NULL,
                total_equity REAL,    -- 當日總資產值
                available_balance REAL, -- 可用餘額
                daily_pnl    REAL,    -- 當日盈虧
                error       TEXT,
                holdings_snapshot TEXT, -- 內容範例：'[{"symbol":"2330","qty":1000,"cost":600}, ...]'
                UNIQUE(strategy_id, run_date), -- 防止同天重複插入
                FOREIGN KEY (strategy_id) REFERENCES strategy(_id)
            );
            CREATE TABLE IF NOT EXISTS trade_record (
                _id         INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT    NOT NULL,
                order_id    TEXT,   -- 儲存券商回傳的委託序號 (如: "O-20260414-001")
                action      TEXT    CHECK(action IN ('BUY', 'SELL')), -- 動作類型
                symbol      TEXT    NOT NULL,
                quantity    INTEGER,     -- 張數/股數
                price       REAL,     -- 成交價
                status      TEXT    NOT NULL DEFAULT 'PENDING', -- 狀態控管 'PENDING' (掛單中), 'FILLED' (完全成交), 'PARTIAL' (部分成交), 'CANCELLED' (已取消), 'FAILED' (失敗)
                result      TEXT,
                pnl           REAL DEFAULT 0,    -- 損益 (僅限 SELL)
                fee           REAL DEFAULT 0,    -- 手續費
                return_rate   REAL DEFAULT 0,    -- 報酬率
                error       TEXT,
                create_at TEXT    NOT NULL, -- YYYY-MM-DD
                update_at     TEXT,    -- 成交或取消時更新
                FOREIGN KEY (strategy_id) REFERENCES strategy(_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_trade_strategy_id ON trade_record(strategy_id);
            CREATE INDEX IF NOT EXISTS idx_trade_symbol ON trade_record(symbol);
        """)
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# strategy
# ---------------------------------------------------------------------------

def create_strategy(
    initial_capital: float,
    partition: int,
    volume_multiplier: float,
    concentration_slope: float,
    atr_multiplier: float,
    back_test_period: int,
) -> dict:
    strategy_id = str(uuid.uuid4())
    now = get_datetime_tw()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO strategy
               (_id, initial_capital, partition, volume_multiplier,
                concentration_slope, atr_multiplier, back_test_period, status, create_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
            (strategy_id, initial_capital, partition, volume_multiplier,
             concentration_slope, atr_multiplier, back_test_period, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM strategy WHERE _id = ?", (strategy_id,)).fetchone()
        return dict(row)


def list_strategies(status: str | None = None) -> list[dict]:
    with _connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM strategy WHERE status = ? ORDER BY create_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM strategy ORDER BY create_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def stop_strategy(strategy_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE strategy SET status = 'stopped' WHERE _id = ? AND status = 'active'",
            (strategy_id,),
        )
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# strategy_daily_log
# ---------------------------------------------------------------------------

def insert_daily_log(
    strategy_id: str,
    run_date: str,
    total_equity: float | None = None,
    daily_pnl: float | None = None,
    holdings_snapshot: str | None = None, # 傳入 json.dumps 後的字串
    error: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO strategy_daily_log 
               (strategy_id, run_date, total_equity, daily_pnl, holdings_snapshot, error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (strategy_id, run_date, total_equity, daily_pnl, holdings_snapshot, error),
        )
        conn.commit()


def list_daily_logs(strategy_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM strategy_daily_log WHERE strategy_id = ? ORDER BY run_date DESC",
            (strategy_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# trade_record
# ---------------------------------------------------------------------------

def insert_trade_record(
    strategy_id: str,
    order_id: str,
    action: str,
    symbol: str,
    quantity: int | None,
    price: float | None,
    status: str = "PENDING",
    pnl: float = 0,
    fee: float = 0,
    return_rate: float = 0,
    result: str | None = None,
    error: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO trade_record
               (strategy_id, order_id, action, symbol, quantity, price, status, pnl, fee, return_rate, result, error, create_at, update_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (strategy_id, order_id, action, symbol, quantity, price, status, pnl, fee, return_rate, result, error, get_datetime_tw().isoformat(), get_datetime_tw().isoformat()),
        )
        conn.commit()
        
def update_trade_record(
    record_id: int,
    status: str,  # 'FILLED', 'FAILED', 'CANCELLED'
    filled_qty: int | None = None,
    fee: float = 0,
    pnl: float = 0,
    return_rate: float = 0,
    result: str | None = None,
    error: str | None = None
) -> None:
    """根據資料庫 _id 更新交易狀態與結果"""
    now = get_datetime_tw().isoformat()
    with _connect() as conn:
        conn.execute(
            """UPDATE trade_record 
                SET status = ?, 
                    fee = ?, 
                    pnl = ?, 
                    return_rate = ?, 
                    result = COALESCE(?, result), 
                    error = COALESCE(?, error),
                    update_at = ?
                WHERE _id = ?""",
            (status, filled_qty, fee, pnl, return_rate, result, error, now, record_id),
        )
        conn.commit()


def list_trade_records(strategy_id: str | None = None, limit: int = 100) -> list[dict]:
    with _connect() as conn:
        if strategy_id:
            rows = conn.execute(
                "SELECT * FROM trade_record WHERE strategy_id = ? ORDER BY _id DESC LIMIT ?",
                (strategy_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trade_record ORDER BY _id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

def get_current_available_balance(strategy_id: str) -> float:
    """
    獲取策略當前的可用餘額。
    邏輯：最新一筆 daily_log 的餘額 -> 若無則回傳 strategy 的初始資金。
    """
    with _connect() as conn:
        cursor = conn.cursor()
        
        # 1. 嘗試從每日日誌中抓取最後一次更新的餘額
        # 依照 _id 或 run_date 降序排列，取第一筆
        cursor.execute("""
            SELECT available_balance 
            FROM strategy_daily_log 
            WHERE strategy_id = ? 
            ORDER BY run_date DESC, _id DESC 
            LIMIT 1
        """, (strategy_id,))
        
        log_result = cursor.fetchone()
        
        if log_result and log_result[0] is not None:
            return float(log_result[0])
        
        # 2. 如果沒有 log 紀錄，則抓取初始資金
        cursor.execute("""
            SELECT initial_capital
            FROM strategy
            WHERE _id = ?
        """, (strategy_id,))
        
        strategy_result = cursor.fetchone()
        
        if strategy_result:
            return float(strategy_result[0])
        
        # 3. 如果連策略都不存在，拋出錯誤或回傳 0
        raise ValueError(f"Strategy ID '{strategy_id}' not found.")
    
def get_current_holdings(strategy_id: str) -> List[Dict[str, Any]]:
    """
    獲取策略當前的持倉快照。
    邏輯：從最新的 daily_log 中讀取 holdings_snapshot 欄位。
    [{"symbol":"2330","qty":1000,"cost":600}, ...}]
    """
    with _connect() as conn:
        cursor = conn.cursor()
        
        # 抓取最後一筆紀錄的持倉快照
        cursor.execute("""
            SELECT holdings_snapshot 
            FROM strategy_daily_log 
            WHERE strategy_id = ? 
            ORDER BY run_date DESC, _id DESC 
            LIMIT 1
        """, (strategy_id,))
        
        result = cursor.fetchone()
        
        # 如果有紀錄且欄位不為空
        if result and result[0]:
            try:
                # 將 TEXT (JSON String) 轉回 Python List/Dict
                return json.loads(result[0])
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse holdings for {strategy_id}")
        
        # 若無紀錄（新策略），回傳空列表
        return []