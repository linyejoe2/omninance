"""
order_record_repo.py — data access for the order_record table.

Sessions are caller-owned; no commits inside. Same-day duplicate protection
is an explicit query (has_order_today) instead of the old functional unique
index on cast(create_at, Date), which also blocked legitimate re-entries
after a failed order.
"""
import logging
from datetime import date
from typing import List, Optional

from sqlalchemy import Date, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select

from src.core.date_time_util import get_datetime_tw
from src.models.trading import OrderRecord, OrderStatus

logger = logging.getLogger(__name__)

# Statuses that should NOT block another attempt on the same symbol today
_RETRIABLE_STATUSES = {OrderStatus.FAILED, OrderStatus.CANCELLED}


async def create_order(session: AsyncSession, order: OrderRecord) -> OrderRecord:
    session.add(order)
    await session.flush()
    await session.refresh(order)
    return order


async def get_order(session: AsyncSession, order_id: int) -> Optional[OrderRecord]:
    return await session.get(OrderRecord, order_id)


async def get_orders_by_ids(session: AsyncSession, ids: List[int]) -> List[OrderRecord]:
    if not ids:
        return []
    statement = select(OrderRecord).where(OrderRecord.id.in_(ids))
    result = await session.execute(statement)
    return list(result.scalars().all())


async def list_orders(
    session: AsyncSession,
    strategy_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[OrderRecord]:
    statement = select(OrderRecord).order_by(desc(OrderRecord.id))
    if strategy_id is not None:
        statement = statement.where(OrderRecord.strategy_id == strategy_id)
    if limit is not None:
        statement = statement.limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def list_orders_on_date(
    session: AsyncSession, strategy_id: str, target_date: date
) -> List[OrderRecord]:
    statement = (
        select(OrderRecord)
        .where(OrderRecord.strategy_id == strategy_id)
        .where(cast(OrderRecord.create_at, Date) == target_date)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def has_order_today(session: AsyncSession, strategy_id: str, symbol: str) -> bool:
    """True if the symbol already has a live order today (PENDING / PARTIAL /
    FILLED / TIMEOUT). FAILED and CANCELLED orders do not block a retry."""
    today = get_datetime_tw().date()
    statement = (
        select(OrderRecord.id)
        .where(OrderRecord.strategy_id == strategy_id)
        .where(OrderRecord.symbol == symbol)
        .where(cast(OrderRecord.create_at, Date) == today)
        .where(OrderRecord.status.not_in(_RETRIABLE_STATUSES))
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalars().first() is not None


async def update_order(session: AsyncSession, order: OrderRecord, **fields) -> OrderRecord:
    for key, value in fields.items():
        setattr(order, key, value)
    order.update_at = get_datetime_tw()
    session.add(order)
    await session.flush()
    return order
