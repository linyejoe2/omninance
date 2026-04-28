import os
import uuid
import logging
from datetime import datetime, date, time
from typing import List, Optional, Any

from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Relationship, Column, select, desc, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import cast, Date, and_

from src.core.pydantic_util import ensure_pydantic
from src.core.date_time_util import get_datetime_tw, get_date_tw


logger = logging.getLogger(__name__)

# --- 基礎類別（共用欄位） ---
class StrategyBase(SQLModel):
    initial_capital: float                  # 初始資金
    partition: int                          # 分塊大小
    volume_multiplier: float                # 成交量乘數
    concentration_slope: float              # 斜率界線
    atr_multiplier: float                   # ATR 乘數
    status: str = Field(default="active")   # active | stopped

# --- 策略主表 ---
class Strategy(StrategyBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    create_at: datetime = Field(default_factory=datetime.now)
    
    # 關聯
    logs: List["StrategyDailyLog"] = Relationship(back_populates="strategy")
    trades: List["TradeRecord"] = Relationship(back_populates="strategy")
    
class Holding(BaseModel):
    symbol: str
    quantity: int
    cost: float
    current_price: float
    highest_price: float
    stop_price: float
    
class BuyObj(BaseModel):
    symbol: str
    bought: bool = False
    price: Optional[float] = None
    quantity: Optional[int] = None
    
class SellObj(BaseModel):
    symbol: str
    sold: bool = False
    price: float
    quantity: int
    reason: str = "ATR_STOP"

# --- 每日日誌（追蹤移動停損與資產） ---
class StrategyDailyLog(SQLModel, table=True):
    __tablename__ = "strategy_daily_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: str = Field(foreign_key="strategy.id")
    execute_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))                    # 執行時間
    compute_at: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))                    # 計算時間 (應該是昨天下午)
    total_equity: float                                         # 當日總資產值 (執行完後)
    available_balance: float                                    # 可用餘額 (執行完後)
    daily_pnl: Optional[float] = 0.0                            # 當日盈虧 (執行完後)
    error: Optional[str] = None
    
    # 使用 PostgreSQL 的 JSONB 存儲持倉快照與移動停損價
    holdings_snapshot: List[Holding] = Field(default=[], sa_column=Column(JSONB))
    
    # 策略選出的標的
    buy_list: List[BuyObj] = Field(default=[], sa_column=Column(JSONB))
    
    # 觸發移動停損而賣出的明細
    sell_list: List[SellObj] = Field(default=[], sa_column=Column(JSONB))

    strategy: Strategy = Relationship(back_populates="logs")

# --- 交易紀錄 ---
class TradeRecord(SQLModel, table=True):
    __tablename__ = "trade_record"
    __table_args__ = (
        Index(
            "uq_strategy_symbol_date",      # 索引名稱
            "strategy_id",                  # 欄位 1
            "symbol",                       # 欄位 2
            cast(Column("create_at"), Date), # 關鍵：將內容轉為日期（Date）進行比較
            unique=True                     # 強制唯一
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: str = Field(foreign_key="strategy.id")
    order_id: Optional[str] = Field(default=None, index=True)       # 券商傳回的 id ex: Z0190
    action: str                                                     # BUY / SELL
    symbol: str = Field(index=True)                                 # 股票代號
    quantity: Optional[int] = None                                  # 張數
    price: Optional[float] = None                                   # 成交價
    status: str = Field(default="PENDING")                          # 'PENDING' (掛單中), 'FILLED' (完全成交), 'PARTIAL' (部分成交), 'CANCELLED' (已取消), 'FAILED' (失敗)
    pnl: float = 0.0                                                # 損益 (僅限 SELL)  
    fee: float = 0.0                                                # 手續費
    return_rate: float = 0.0                                        # 報酬率
    result: Optional[str] = None
    error: Optional[str] = None
    create_at: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True), default_factory=get_datetime_tw())
    update_at: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True), default_factory=get_datetime_tw())

    strategy: Strategy = Relationship(back_populates="trades")
    
# 建議在 StrategyDailyLog 的 strategy relationship 加上 lazy="joined" 或使用 selectinload

# --- 異步連線設定 ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/omninance")
engine = create_async_engine(DATABASE_URL, echo=False)

async def init_db():
    async with engine.begin() as conn:
        # 異步環境下執行 DDL 需要 run_sync
        await conn.run_sync(SQLModel.metadata.create_all)

# --- 異步資料操作函式 ---

async def create_strategy(data: StrategyBase) -> Strategy:
    async with AsyncSession(engine) as session:
        db_strategy = Strategy.model_validate(data)
        session.add(db_strategy)
        await session.commit()
        await session.refresh(db_strategy)
        return db_strategy
    
async def stop_strategy(strategy_id: str) -> bool:
    """
    將策略狀態改為 stopped，使其不再參與後續的訊號計算與交易。
    """
    async with AsyncSession(engine) as session:
        # 1. 取得策略物件
        strategy = await session.get(Strategy, strategy_id)
        
        # 2. 檢查是否存在或是否已經停止
        if not strategy or strategy.status == "stopped":
            logger.warning(f"Stop request ignored: Strategy {strategy_id} not found or already stopped.")
            return False
        
        # 3. 更新狀態
        strategy.status = "stopped"
        session.add(strategy)
        
        try:
            await session.commit()
            logger.info(f"Strategy {strategy_id} has been successfully stopped.")
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to stop strategy {strategy_id}: {e}")
            return False

async def get_current_available_balance(strategy_id: str) -> float:
    async with AsyncSession(engine) as session:
        # 異步 select 需要 await session.exec
        statement = (
            select(StrategyDailyLog)
            .where(StrategyDailyLog.strategy_id == strategy_id)
            .order_by(desc(StrategyDailyLog.execute_at), desc(StrategyDailyLog.id))
            .limit(1)
        )
        result = await session.execute(statement)
        log = result.scalar_one_or_none()
        
        if log:
            return log.available_balance
        
        logger.info(f"No daily log found for strategy {strategy_id}. Fetching initial capital.")
        
        strategy = await session.get(Strategy, strategy_id)
        if strategy:
            return strategy.initial_capital
        
        raise ValueError(f"Strategy {strategy_id} not found")

async def update_trade_record(record_id: int, **kwargs):
    async with AsyncSession(engine) as session:
        db_record = await session.get(TradeRecord, record_id)
        if not db_record:
            return
        
        for key, value in kwargs.items():
            setattr(db_record, key, value)
        
        db_record.update_at = datetime.now()
        session.add(db_record)
        await session.commit()

async def update_buy_obj(log_id: int, buy_obj: BuyObj) -> Optional[StrategyDailyLog]:
    async with AsyncSession(engine) as session:
        log = await session.get(StrategyDailyLog, log_id)
        if not log:
            return None

        # 使用 map 處理更新邏輯，更簡潔且防呆
        buy_map = {item["symbol"]: item for item in (log.buy_list or [])}
        
        # 更新資訊
        updated_info = buy_obj.model_dump()
        updated_info["bought"] = True
        buy_map[buy_obj.symbol] = updated_info
        
        log.buy_list = list(buy_map.values()) # 重新賦值觸發 SQLModel/JSONB 更新
        
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log

async def update_sell_obj(log_id: int, sell_obj: SellObj) -> Optional[StrategyDailyLog]:
    async with AsyncSession(engine) as session:
        log = await session.get(StrategyDailyLog, log_id)
        if not log:
            logger.warning(f"[DB] Log {log_id} not found")
            return None

        current_list = log.sell_list or []
        sell_map = {item["symbol"]: item for item in current_list}
        
        # 4. 更新或新增資料
        # 直接利用 Pydantic 的 model_dump() 覆蓋或新增
        sell_map[sell_obj.symbol] = sell_obj.model_dump()
        
        # 額外邏輯：確保 sold 標記為 True (如果 sell_obj 傳入時沒設)
        sell_map[sell_obj.symbol]["sold"] = True

        # 5. 重新賦值以觸發 SQLAlchemy 的變動偵測 (Assignment triggers change)
        log.sell_list = list(sell_map.values())
        
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log
    
async def add_sell_obj(log_id: int, sell_obj: SellObj) -> Optional[StrategyDailyLog]:
    async with AsyncSession(engine) as session:
        log = await session.get(StrategyDailyLog, log_id)
        if not log:
            logger.error(f"[DB] StrategyDailyLog {log_id} not found.")
            return None

        # 2. 準備新的列表 (處理可能的 None 或初始化)
        current_sell_list = list(log.sell_list) if log.sell_list else []
        
        # 3. 新增賣出物件
        # 注意：確保 sell_obj 已經是 dict 或符合 JSON 序列化的格式
        current_sell_list.append(sell_obj)
        
        # 4. 重新賦值以觸發 SQLAlchemy Mutation Tracking
        log.sell_list = current_sell_list
        
        try:
            session.add(log)
            # 保險起見，明確標記該欄位已修改
            flag_modified(log, "sell_list")
            
            await session.commit()
            await session.refresh(log)
            logger.info(f"[DB] Added {sell_obj.symbol} to sell_list of log {log_id}")
            return log
        except Exception as e:
            session.rollback()
            logger.error(f"[DB] Failed to update sell_list: {e}")
            return None

async def get_current_holdings(strategy_id: str) -> List[Holding]:
    """
    獲取策略當前的持倉快照。
    邏輯：從最新的 daily_log 中讀取 holdings_snapshot 欄位。
    """
    async with AsyncSession(engine) as session:
        statement = (
            select(StrategyDailyLog)
            .where(StrategyDailyLog.strategy_id == strategy_id)
            .order_by(desc(StrategyDailyLog.execute_at), desc(StrategyDailyLog.id))
            .limit(1)
        )
        result = await session.execute(statement)
        log = result.scalars().first()
        
        if log and log.holdings_snapshot:
            return ensure_pydantic(log.holdings_snapshot, list[Holding])
        
        
        # 如果找不到紀錄，輸出 INFO 並回傳空清單（代表新策略尚未建倉）
        logger.info(f"No holdings snapshot found for strategy {strategy_id}. Returning empty list.")
        return []
    
async def get_trade_records_by_ids(ids: List[int]) -> List[TradeRecord]:
    """
    透過主鍵 ID 清單獲取交易紀錄。
    SQLModel 會自動處理 PostgreSQL 的 IN 查詢。
    """
    if not ids:
        return []

    async with AsyncSession(engine) as session:
        # 使用 .where() 配合 TradeRecord.id.in_(ids) 語法
        statement = select(TradeRecord).where(TradeRecord.id.in_(ids))
        
        results = await session.execute(statement)
        records = results.scalars().all()
        # 返回 TradeRecord 物件清單
        # 如果你後續需要 dict 格式，可以使用 [r.model_dump() for r in results]
        return list(records)
    
async def list_trade_records(strategy_id: str, limit: int|None = None) -> list[TradeRecord]:
    """撈出 Daily Log List"""
    async with AsyncSession(engine) as session:
        statement = select(TradeRecord).where(TradeRecord.strategy_id == strategy_id).order_by(desc(TradeRecord.id))
        if limit:
            statement = statement.limit(limit)
        result = await session.execute(statement)
        return list(result.scalars().all())

async def save_trade_record(record: TradeRecord) -> int | None:
    """負責將交易紀錄寫入資料庫，並處理異步 Session 事務"""
    async with AsyncSession(engine) as session:
        try:
            # 確保時區正確 (Naive)
            if record.create_at:
                record.create_at = record.create_at.replace(tzinfo=None)
            if record.update_at:
                record.update_at = record.update_at.replace(tzinfo=None)
                
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record.id
        except Exception as e:
            await session.rollback()
            logger.error(f"[DB] save_trade_record failed: {e}")
            return None

async def get_activated_strategies() -> List[Strategy]:
    """撈出所有運行中的策略"""
    async with AsyncSession(engine) as session:
        statement = select(Strategy).where(Strategy.status == "active")
        result = await session.execute(statement)
        return list(result.scalars().all())
    
async def get_strategy(strategy_id: str) -> Strategy:
    """撈出單一策略"""
    async with AsyncSession(engine) as session:
        return await session.get(Strategy, strategy_id)
    
async def get_strategies(status: str | None = None) -> List[Strategy]:
    """根據狀態撈出策略，若無指定則撈出全部"""
    async with AsyncSession(engine) as session:
        statement = select(Strategy)
        
        # 動態增加篩選條件
        if status:
            statement = statement.where(Strategy.status == status)
            
        result = await session.execute(statement)
        
        # 關鍵修正：使用 .scalars() 移除 Row Tuple
        return list(result.scalars().all())
    
async def get_daily_log(id: int) -> StrategyDailyLog:
    """撈出單一 Daily Log"""
    async with AsyncSession(engine) as session:
        return await session.get(StrategyDailyLog, id)
    
async def list_daily_logs(strategy_id: str) -> list[StrategyDailyLog]:
    """撈出 Daily Log List"""
    async with AsyncSession(engine) as session:
        statement = select(StrategyDailyLog).where(StrategyDailyLog.strategy_id == strategy_id).order_by(desc(StrategyDailyLog.id))
        result = await session.execute(statement)
        return list(result.scalars().all())
    
async def get_last_daily_log(strategy_id: str) -> StrategyDailyLog:
    """撈出最後一筆 Daily Log"""
    async with AsyncSession(engine) as session:
        statement = select(StrategyDailyLog).where(StrategyDailyLog.strategy_id == strategy_id).order_by(desc(StrategyDailyLog.id)).limit(1)
        result = await session.execute(statement)
        log = result.scalars().first()
        return log
    
async def get_last_unexecuted_daily_log(strategy_id: str) -> StrategyDailyLog:
    """撈出最後一筆 Daily Log"""
    async with AsyncSession(engine) as session:
        statement = select(StrategyDailyLog).where(StrategyDailyLog.strategy_id == strategy_id).where(StrategyDailyLog.execute_at == None).order_by(desc(StrategyDailyLog.id)).limit(1)
        result = await session.execute(statement)
        log = result.scalars().first()
        return log
    
async def set_daily_log_to_executed(log_id: int) -> None:
    async with AsyncSession(engine) as session:
        log = await session.get(StrategyDailyLog, log_id)
        if log:
            log.execute_at = get_datetime_tw()
            session.add(log)
            await session.commit()
            
async def get_today_executed_daily_log(strategy_id: str) -> StrategyDailyLog:
    async with AsyncSession(engine) as session:
        statement = (
        select(StrategyDailyLog)
        .where(StrategyDailyLog.strategy_id == strategy_id)
        .where(cast(StrategyDailyLog.execute_at, Date) == get_date_tw())
        .limit(1)
        )
        result = await session.execute(statement)
        return result.scalars().first()

async def get_privous_daily_log(log_id: int) -> StrategyDailyLog:
    async with AsyncSession(engine) as session:
        statement = (
            select(StrategyDailyLog)
            .where(StrategyDailyLog.id < log_id)
            .order_by(desc(StrategyDailyLog.id))
            .limit(1)
        )
        result = await session.execute(statement)
        return result.scalars().first()

async def check_log_exists_for_post_market(strategy_id: str, target_date: date) -> bool:
    """
    檢查該策略在特定日期的『盤後 (14:00 以後)』是否已經生成過紀錄
    """
    # 定義「盤後」的起始時間點
    # 假設 14:00 以後產生的才算盤後訊號
    post_market_start = datetime.combine(target_date, time(14, 0, 0))

    async with AsyncSession(engine) as session:
        statement = (
            select(StrategyDailyLog)
            .where(StrategyDailyLog.strategy_id == strategy_id)
            # 條件 1：日期必須是今天
            .where(cast(StrategyDailyLog.compute_at, Date) == target_date)
            # 條件 2：時間必須在 14:00 之後
            .where(StrategyDailyLog.compute_at >= post_market_start)
            .limit(1)
        )
        result = await session.execute(statement)
        return result.scalars().first() is not None

async def save_strategy_daily_log(log_data: StrategyDailyLog) -> StrategyDailyLog:
    async with AsyncSession(engine) as session:
        try:
            session.add(log_data)
            await session.commit()
            await session.refresh(log_data)
            return log_data
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to save Daily Log: {e}")
            raise
        
async def is_symbol_traded_today(strategy_id: str, symbol: str) -> bool:
    """檢查特定標的是否在今天已經有交易紀錄（包含掛單中、成功、失敗）"""
    today = get_date_tw()
    
    async with AsyncSession(engine) as session:
        statement = (
            select(TradeRecord)
            .where(
                and_(
                    TradeRecord.strategy_id == strategy_id,
                    TradeRecord.symbol == symbol,
                    cast(TradeRecord.create_at, Date) == today
                )
            )
            .limit(1)
        )
        result = await session.execute(statement)
        return result.scalars().first() is not None