"""
db.py — SQLite persistence for strategy management.

Schema:
  strategy(_id, initial_capital, partition, volume_multiplier,
           concentration_slope, atr_multiplier, back_test_period,
           status, create_date)
  strategy_daily_log(_id, strategy_id, run_date, buy_count, sell_count, error)
  trade_record(_id, strategy_id, action, symbol, quantity, price,
               result, error, create_date)
"""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from core.date_time_util import get_now_iso

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
                create_date         TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategy_daily_log (
                _id         INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT    NOT NULL,
                run_date    TEXT    NOT NULL,
                buy_count   INTEGER,
                sell_count  INTEGER,
                error       TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategy(_id)
            );
            CREATE TABLE IF NOT EXISTS trade_record (
                _id         INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT    NOT NULL,
                action      TEXT    NOT NULL,
                symbol      TEXT    NOT NULL,
                quantity    INTEGER,
                price       REAL,
                result      TEXT,
                error       TEXT,
                create_date TEXT    NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategy(_id)
            );
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
    now = get_now_iso()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO strategy
               (_id, initial_capital, partition, volume_multiplier,
                concentration_slope, atr_multiplier, back_test_period, status, create_date)
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
                "SELECT * FROM strategy WHERE status = ? ORDER BY create_date DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM strategy ORDER BY create_date DESC"
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
    buy_count: int | None,
    sell_count: int | None,
    error: str | None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO strategy_daily_log (strategy_id, run_date, buy_count, sell_count, error)
               VALUES (?, ?, ?, ?, ?)""",
            (strategy_id, run_date, buy_count, sell_count, error),
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
    action: str,
    symbol: str,
    quantity: int | None,
    price: float | None,
    result: str | None,
    error: str | None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO trade_record
               (strategy_id, action, symbol, quantity, price, result, error, create_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (strategy_id, action, symbol, quantity, price, result, error, _now_iso()),
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
