"""
position_repo.py — data access for the position table (current holdings).

The position table is the single source of truth for what a strategy holds —
fills mutate rows here instead of rewriting a JSONB snapshot. Sessions are
caller-owned; no commits inside.
"""
import logging
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.date_time_util import get_datetime_tw
from src.models.trading import Position

logger = logging.getLogger(__name__)


async def list_positions(session: AsyncSession, strategy_id: str) -> List[Position]:
    statement = (
        select(Position).where(Position.strategy_id == strategy_id).order_by(Position.symbol)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_position(
    session: AsyncSession, strategy_id: str, symbol: str
) -> Optional[Position]:
    statement = (
        select(Position)
        .where(Position.strategy_id == strategy_id)
        .where(Position.symbol == symbol)
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalars().first()


async def apply_buy_fill(
    session: AsyncSession,
    strategy_id: str,
    symbol: str,
    quantity: int,
    price: Decimal,
) -> Position:
    """Create the position, or add to it with a weighted average cost."""
    position = await get_position(session, strategy_id, symbol)
    if position is None:
        position = Position(
            strategy_id=strategy_id,
            symbol=symbol,
            quantity=quantity,
            average_cost=price,
            current_price=price,
            highest_price=price,
            trailing_stop_price=Decimal("0"),
        )
    else:
        total_qty = position.quantity + quantity
        position.average_cost = (
            position.average_cost * position.quantity + price * quantity
        ) / total_qty
        position.quantity = total_qty
        position.current_price = price
        position.highest_price = max(position.highest_price, price)
        position.update_at = get_datetime_tw()
    session.add(position)
    await session.flush()
    return position


async def apply_sell_fill(
    session: AsyncSession,
    strategy_id: str,
    symbol: str,
    quantity: int,
) -> Optional[Decimal]:
    """Reduce (or close) the position; returns the average cost of the sold
    shares for realized-PnL calculation, or None if no position existed."""
    position = await get_position(session, strategy_id, symbol)
    if position is None:
        logger.warning(f"[PositionRepo] Sell fill for {symbol} with no open position ({strategy_id})")
        return None

    average_cost = position.average_cost
    if quantity >= position.quantity:
        await session.delete(position)
    else:
        position.quantity -= quantity
        position.update_at = get_datetime_tw()
        session.add(position)
    await session.flush()
    return average_cost


async def update_market_data(
    session: AsyncSession,
    position: Position,
    current_price: Decimal,
    trailing_stop_price: Optional[Decimal] = None,
) -> Position:
    """Refresh quote-derived fields. highest_price only moves up; the
    trailing stop only moves up (移動停損原則)."""
    position.current_price = current_price
    position.highest_price = max(position.highest_price, current_price)
    if trailing_stop_price is not None:
        position.trailing_stop_price = max(position.trailing_stop_price, trailing_stop_price)
    position.update_at = get_datetime_tw()
    session.add(position)
    await session.flush()
    return position
