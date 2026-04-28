import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Relationship, Column, JSON, create_engine, Session, select, desc
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from src.core.pydantic_util import ensure_pydantic

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
    execute_at: Optional[datetime] = Field(default=None, index=True)                    # 執行時間
    compute_at: datetime = Field(index=True)                    # 計算時間 (應該是昨天下午)
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
    create_at: datetime = Field(default_factory=datetime.now)
    update_at: datetime = Field(default_factory=datetime.now)

    strategy: Strategy = Relationship(back_populates="trades")
    

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/omninance")
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)
    
def create_strategy(data: StrategyBase) -> Strategy:
    with Session(engine) as session:
        db_strategy = Strategy.model_validate(data)
        session.add(db_strategy)
        session.commit()
        session.refresh(db_strategy)
        return db_strategy
    
def get_current_available_balance(strategy_id: str) -> float:
    with Session(engine) as session:
        # 1. 找最後一筆 Daily Log
        statement = select(StrategyDailyLog).where(
            StrategyDailyLog.strategy_id == strategy_id
        ).order_constraint(desc(StrategyDailyLog.execute_at), desc(StrategyDailyLog.id)).limit(1)
        
        log = session.exec(statement).first()
        if log:
            return log.available_balance
        
        # 2. 找不到 Log 的情況
        logger.info(f"No daily log found for strategy {strategy_id}. Fetching initial capital.")
        
        strategy = session.get(Strategy, strategy_id)
        if strategy:
            return strategy.initial_capital
        
        raise ValueError(f"Strategy {strategy_id} not found")
    
def update_trade_record(record_id: int, **kwargs):
    with Session(engine) as session:
        db_record = session.get(TradeRecord, record_id)
        if not db_record:
            return
        
        for key, value in kwargs.items():
            setattr(db_record, key, value)
        
        db_record.update_at = datetime.now()
        session.add(db_record)
        session.commit()
        
def update_buy_obj(log_id: int, buy_obj: BuyObj) -> Optional[StrategyDailyLog]:
    with Session(engine) as session:
        log = session.get(StrategyDailyLog, log_id)
        if not log:
            return None

        # 修改內部的 List (SQLModel 會處理 Pydantic 模型與 JSON 轉換)
        # 為了保險，我們直接建立一個新的 list 來觸發 SQLAlchemy 的 setter
        new_list = []
        for obj in log.buy_list:
            if obj.symbol == buy_obj.symbol:
                obj.bought = True
                obj.price = buy_obj.price
                obj.quantity = buy_obj.quantity
            new_list.append(obj)
        
        log.buy_list = new_list # 重新賦值觸發更新
        
        session.add(log)
        session.commit()
        session.refresh(log)
        return log
    
def update_sell_obj(log_id: int, sell_obj: SellObj) -> Optional[StrategyDailyLog]:
    with Session(engine) as session:
        # 1. 使用 get 抓取資料
        log = session.get(StrategyDailyLog, log_id)
        if not log:
            logger.warning(f"[DB] Log {log_id} not found")
            return None

        # 2. 獲取原始清單 (確保是 list)
        current_list = log.sell_list or []
        
        # 3. 使用 dict 結構處理更新，效能與邏輯更清晰
        # 將原本的 list 轉成以 symbol 為 key 的 dict
        sell_map = {item["symbol"]: item for item in current_list}
        
        # 4. 更新或新增資料
        # 直接利用 Pydantic 的 model_dump() 覆蓋或新增
        sell_map[sell_obj.symbol] = sell_obj.model_dump()
        
        # 額外邏輯：確保 sold 標記為 True (如果 sell_obj 傳入時沒設)
        sell_map[sell_obj.symbol]["sold"] = True

        # 5. 重新賦值以觸發 SQLAlchemy 的變動偵測 (Assignment triggers change)
        log.sell_list = list(sell_map.values())
        
        # 6. 提交
        session.add(log)
        session.commit()
        session.refresh(log) # 刷新物件狀態
        return log

def add_sell_obj(log_id: int, sell_obj: SellObj) -> Optional[StrategyDailyLog]:
    with Session(engine) as session:
        log = session.get(StrategyDailyLog, log_id)
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
            
            session.commit()
            session.refresh(log)
            logger.info(f"[DB] Added {sell_obj.symbol} to sell_list of log {log_id}")
            return log
        except Exception as e:
            session.rollback()
            logger.error(f"[DB] Failed to update sell_list: {e}")
            return None
        
def get_current_holdings(strategy_id: str) -> List[Holding]:
    """
    獲取策略當前的持倉快照。
    邏輯：從最新的 daily_log 中讀取 holdings_snapshot 欄位。
    """
    with Session(engine) as session:
        # 使用你設定的 execute_at 和 id 進行降序排列，確保拿到最新的一筆
        statement = (
            select(StrategyDailyLog)
            .where(StrategyDailyLog.strategy_id == strategy_id)
            .order_by(
                desc(StrategyDailyLog.execute_at), 
                desc(StrategyDailyLog.id)
            )
            .limit(1)
        )
        
        result = session.exec(statement).first()
        
        # SQLModel 配合 PostgreSQL 的 JSONB 欄位會自動將資料轉為 Python List[Dict]
        # 不需要再使用 json.loads()
        if result and result.holdings_snapshot:
            return result.holdings_snapshot
        
        # 如果找不到紀錄，輸出 INFO 並回傳空清單（代表新策略尚未建倉）
        logger.info(f"No holdings snapshot found for strategy {strategy_id}. Returning empty list.")
        return []
    
def get_trade_records_by_ids(ids: List[int]) -> List[TradeRecord]:
    """
    透過主鍵 ID 清單獲取交易紀錄。
    SQLModel 會自動處理 PostgreSQL 的 IN 查詢。
    """
    if not ids:
        return []

    with Session(engine) as session:
        # 使用 .where() 配合 TradeRecord.id.in_(ids) 語法
        statement = select(TradeRecord).where(TradeRecord.id.in_(ids))
        
        results = session.exec(statement).all()
        
        # 返回 TradeRecord 物件清單
        # 如果你後續需要 dict 格式，可以使用 [r.model_dump() for r in results]
        return list(results)
    
def get_activated_strategies() -> List[Strategy]:
    """撈出所有運行中的策略"""
    with Session(engine) as session:
        statement = select(Strategy).where(Strategy.status == "active")
        return session.exec(statement).all()
    
def get_strategy(strategy_id: str) -> Strategy:
    """撈出單一策略"""
    with Session(engine) as session:
        return session.get(Strategy, strategy_id)
    
def get_daily_log(id: int) -> StrategyDailyLog:
    """撈出單一 Daily Log"""
    with Session(engine) as session:
        return session.get(StrategyDailyLog, id)
    
def get_last_daily_log(strategy_id: str) -> StrategyDailyLog:
    """撈出最後一筆 Daily Log"""
    with Session(engine) as session:
        statement = select(StrategyDailyLog).where(StrategyDailyLog.strategy_id == strategy_id).order_by(desc(StrategyDailyLog.id)).limit(1)
        return session.exec(statement).first()
    
def get_last_unexecuted_daily_log(strategy_id: str) -> StrategyDailyLog:
    """撈出最後一筆 Daily Log"""
    with Session(engine) as session:
        statement = select(StrategyDailyLog).where(StrategyDailyLog.strategy_id == strategy_id).where(StrategyDailyLog.execute_at == None).order_by(desc(StrategyDailyLog.id)).limit(1)
        return session.exec(statement).first()
    
def save_strategy_daily_log(log_data: StrategyDailyLog) -> StrategyDailyLog:
    with Session(engine) as session:
        try:
            # 如果物件已經有 ID，則會自動處理為更新 (Merge)
            # 如果沒有 ID，則會新增 (Add)
            session.add(log_data)
            session.commit()
            session.refresh(log_data) # 確保物件拿到資料庫生成的 ID
            return log_data
        except Exception as e:
            session.rollback() # 發生錯誤時回滾
            logger.error(f"Failed to save Daily Log: {e}")
            raise