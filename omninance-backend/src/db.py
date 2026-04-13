"""
db.py — SQLite persistence for strategy execution history.

Schema:
  execution(_id, action, symbol, quantity, price, result, error, create_date)
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_DB_PATH = Path("/app/data/omninance.db")


def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution (
                _id         INTEGER PRIMARY KEY AUTOINCREMENT,
                action      TEXT    NOT NULL,
                symbol      TEXT    NOT NULL,
                quantity    INTEGER,
                price       REAL,
                result      TEXT,
                error       TEXT,
                create_date TEXT    NOT NULL
            )
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


def insert_execution(
    action: str,
    symbol: str,
    quantity: int,
    price: float | None,
    result: str | None,
    error: str | None,
    create_date: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO execution (action, symbol, quantity, price, result, error, create_date)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (action, symbol, quantity, price, result, error, create_date),
        )
        conn.commit()


def list_executions(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM execution ORDER BY _id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
