"""
daily_log_repo.py — data access for the strategy_daily_log table.

One row per strategy per record_date (DB-enforced), moved through the
DailyLogStatus lifecycle. Sessions are caller-owned; no commits inside.
"""
import logging
from datetime import date
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select

from src.models.trading import DailyLogStatus, StrategyDailyLog

logger = logging.getLogger(__name__)


async def create_log(session: AsyncSession, log: StrategyDailyLog) -> StrategyDailyLog:
    session.add(log)
    await session.flush()
    await session.refresh(log)
    return log


async def get_log(session: AsyncSession, log_id: int) -> Optional[StrategyDailyLog]:
    return await session.get(StrategyDailyLog, log_id)


async def get_log_by_date(
    session: AsyncSession, strategy_id: str, record_date: date
) -> Optional[StrategyDailyLog]:
    statement = (
        select(StrategyDailyLog)
        .where(StrategyDailyLog.strategy_id == strategy_id)
        .where(StrategyDailyLog.record_date == record_date)
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalars().first()


async def get_latest_log(
    session: AsyncSession,
    strategy_id: str,
    status: Optional[DailyLogStatus] = None,
) -> Optional[StrategyDailyLog]:
    statement = (
        select(StrategyDailyLog)
        .where(StrategyDailyLog.strategy_id == strategy_id)
        .order_by(desc(StrategyDailyLog.record_date), desc(StrategyDailyLog.id))
        .limit(1)
    )
    if status is not None:
        statement = statement.where(StrategyDailyLog.status == status)
    result = await session.execute(statement)
    return result.scalars().first()


async def get_latest_ended_log(
    session: AsyncSession, strategy_id: str
) -> Optional[StrategyDailyLog]:
    """Most recent settled log — the balance/equity baseline for the next day."""
    return await get_latest_log(session, strategy_id, DailyLogStatus.ENDED)


async def list_logs(
    session: AsyncSession, strategy_id: str, limit: Optional[int] = None
) -> List[StrategyDailyLog]:
    statement = (
        select(StrategyDailyLog)
        .where(StrategyDailyLog.strategy_id == strategy_id)
        .order_by(desc(StrategyDailyLog.record_date), desc(StrategyDailyLog.id))
    )
    if limit is not None:
        statement = statement.limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def append_error(session: AsyncSession, log: StrategyDailyLog, message: str) -> None:
    """Append to the errors list — reassigns the column so the JSON change is tracked."""
    log.errors = [*(log.errors or []), message]
    session.add(log)
    await session.flush()
