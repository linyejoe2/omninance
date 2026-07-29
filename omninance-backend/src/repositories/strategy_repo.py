"""
strategy_repo.py — data access for the strategy table.

Every function takes an AsyncSession and never commits — the caller owns the
transaction (unit-of-work), so multi-table changes stay atomic.
"""
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.trading import Strategy, StrategyStatus

logger = logging.getLogger(__name__)


async def create_strategy(session: AsyncSession, strategy: Strategy) -> Strategy:
    session.add(strategy)
    await session.flush()
    await session.refresh(strategy)
    return strategy


async def get_strategy(session: AsyncSession, strategy_id: str) -> Optional[Strategy]:
    return await session.get(Strategy, strategy_id)


async def list_strategies(
    session: AsyncSession, status: Optional[StrategyStatus] = None
) -> List[Strategy]:
    statement = select(Strategy).order_by(Strategy.create_at.desc())
    if status is not None:
        statement = statement.where(Strategy.status == status)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def list_active_strategies(session: AsyncSession) -> List[Strategy]:
    return await list_strategies(session, StrategyStatus.ACTIVE)


async def stop_strategy(session: AsyncSession, strategy_id: str) -> bool:
    strategy = await session.get(Strategy, strategy_id)
    if not strategy or strategy.status == StrategyStatus.STOPPED:
        logger.warning(f"[StrategyRepo] Stop ignored: {strategy_id} not found or already stopped")
        return False
    strategy.status = StrategyStatus.STOPPED
    session.add(strategy)
    return True
