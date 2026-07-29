"""
trading.py — SQLModel table definitions for the PostgreSQL trading store.

Finance data lives in PostgreSQL for safety (Decimal money columns, FK
integrity, enum-constrained statuses); high-volume market data stays in
MongoDB (see src/models/db.py).

Tables:
  strategy           — strategy configuration
  position           — current open positions per strategy (source of truth
                       for holdings; replaces the holdings_snapshot JSONB
                       that used to be mutated in place)
  order_record       — every broker order with request/fill breakdown,
                       fee/tax and realized PnL (replaces trade_record)
  strategy_daily_log — one row per strategy per trading day, driven through
                       an explicit status lifecycle; JSONB is kept only for
                       immutable snapshots (holdings at signal time, raw
                       model signals) and per-day error notes
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel
from sqlalchemy import JSON, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from src.core.date_time_util import get_datetime_tw


class StrategyStatus(str, Enum):
    ACTIVE = "active"
    STOPPED = "stopped"


class OrderAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"      # 掛單中
    PARTIAL = "PARTIAL"      # 部分成交
    FILLED = "FILLED"        # 完全成交
    CANCELLED = "CANCELLED"  # 已取消
    FAILED = "FAILED"        # 失敗
    TIMEOUT = "TIMEOUT"      # 輪詢逾時，成交狀態未知


class SellReason(str, Enum):
    TRAILING_STOP = "TRAILING_STOP"  # 移動停損觸發
    SIGNAL_EXIT = "SIGNAL_EXIT"      # 籌碼訊號消失
    MANUAL = "MANUAL"                # 手動賣出


class DailyLogStatus(str, Enum):
    SIGNAL_GENERATED = "signal-generated"  # 15:30 前一日盤後：訊號已產生
    EXECUTING = "executing"                # 09:00-13:30 盤中：執行買賣
    FINALIZING = "finalizing"              # 15:00 盤後：結算中
    ENDED = "ended"                        # 結算完成


# --- 1. 策略配置表 ---
class Strategy(SQLModel, table=True):
    __tablename__ = "strategy"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    initial_capital: Decimal = Field(sa_column=Column(Numeric(18, 8)))
    position_slots: int                     # 資金分成幾份（原 partition）
    volume_multiplier: float                # 成交量乘數
    concentration_slope: float              # 籌碼集中度斜率界線
    atr_multiplier: float                   # 移動停損 ATR 乘數
    status: StrategyStatus = Field(default=StrategyStatus.ACTIVE, index=True)
    create_at: datetime = Field(
        default_factory=get_datetime_tw, sa_column=Column(DateTime(timezone=True))
    )

    positions: List["Position"] = Relationship(back_populates="strategy")
    orders: List["OrderRecord"] = Relationship(back_populates="strategy")
    daily_logs: List["StrategyDailyLog"] = Relationship(back_populates="strategy")


# --- 2. 當前持倉部位 ---
class Position(SQLModel, table=True):
    __tablename__ = "position"

    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: str = Field(foreign_key="strategy.id", index=True)
    symbol: str = Field(index=True)
    quantity: int = Field(default=0)        # 股數

    average_cost: Decimal = Field(sa_column=Column(Numeric(18, 8)))
    current_price: Decimal = Field(sa_column=Column(Numeric(18, 8)))
    highest_price: Decimal = Field(sa_column=Column(Numeric(18, 8)))
    trailing_stop_price: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 8)))

    create_at: datetime = Field(
        default_factory=get_datetime_tw, sa_column=Column(DateTime(timezone=True), index=True)
    )
    update_at: datetime = Field(
        default_factory=get_datetime_tw, sa_column=Column(DateTime(timezone=True))
    )

    strategy: Strategy = Relationship(back_populates="positions")


# --- 3. 委託單與交易紀錄 ---
class OrderRecord(SQLModel, table=True):
    __tablename__ = "order_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: str = Field(foreign_key="strategy.id", index=True)
    broker_order_id: Optional[str] = Field(default=None, index=True)  # 券商委託書號 ex: Z0190

    symbol: str = Field(index=True)
    action: OrderAction
    status: OrderStatus = Field(default=OrderStatus.PENDING, index=True)
    sell_reason: Optional[SellReason] = None  # 僅賣單：賣出原因

    req_quantity: int                        # 委託股數
    req_price: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    filled_quantity: int = Field(default=0)  # 實際成交股數（處理部分成交）
    filled_price: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))  # 成交均價

    fee: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(10, 2)))
    tax: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(10, 2)))  # 台股賣出證交稅
    realized_pnl: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 4)))  # 實現損益（僅賣單）
    return_rate: float = Field(default=0.0)  # 報酬率 %

    error_msg: Optional[str] = None
    create_at: datetime = Field(
        default_factory=get_datetime_tw, sa_column=Column(DateTime(timezone=True), index=True)
    )
    update_at: datetime = Field(
        default_factory=get_datetime_tw, sa_column=Column(DateTime(timezone=True))
    )

    strategy: Strategy = Relationship(back_populates="orders")


# --- 4. 每日資產結算與快照 ---
class StrategyDailyLog(SQLModel, table=True):
    __tablename__ = "strategy_daily_log"
    # 一個策略一天只有一本帳。純欄位組合的約束，取代舊 trade_record 上
    # cast(create_at, Date) 的危險函數式唯一索引。
    __table_args__ = (
        UniqueConstraint("strategy_id", "record_date", name="uq_strategy_daily_log_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: str = Field(foreign_key="strategy.id", index=True)
    status: DailyLogStatus = Field(default=DailyLogStatus.SIGNAL_GENERATED, index=True)

    record_date: date = Field(index=True)   # 這筆日誌記的是哪一天的帳
    execute_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    total_equity: Decimal = Field(sa_column=Column(Numeric(18, 4)))
    available_balance: Decimal = Field(sa_column=Column(Numeric(18, 4)))
    daily_pnl: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 4)))

    # JSONB 僅用於「不可變快照」：訊號產生當下的持倉與模型原始訊號，
    # 供除錯與回放；當前持倉的真相在 position 表，不再於 JSONB 內就地修改。
    holdings_snapshot: list = Field(default_factory=list, sa_column=Column(JSONB))
    buy_signals_snapshot: list = Field(default_factory=list, sa_column=Column(JSONB))
    sell_signals_snapshot: list = Field(default_factory=list, sa_column=Column(JSONB))

    errors: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    strategy: Strategy = Relationship(back_populates="daily_logs")
