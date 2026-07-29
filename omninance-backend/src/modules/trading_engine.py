"""
trading_engine.py — core trading workflow, one function per scheduled phase.

Daily lifecycle of a StrategyDailyLog (status column):

  15:30 D-1  generate_daily_signals()    → creates log(record_date=D) with
                                           status SIGNAL_GENERATED; updates
                                           position trailing stops from the
                                           chip-tracker snapshot
  09:00-13:30 D  execute_daily_strategy() → SIGNAL_GENERATED → EXECUTING;
                                           places stop-loss sells then buys,
                                           polls fills in the background
  15:00 D    finalize_daily_settlement()  → EXECUTING → FINALIZING → ENDED;
                                           marks positions to market and
                                           settles equity / daily PnL

All money flows through Decimal; the position table is the source of truth
for holdings; fills update order_record + position + the day's log balance
inside a single transaction per poll event.
"""
import asyncio
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from src.core.date_time_util import get_action_date, get_date_tw, get_datetime_tw
from src.core.decimal_util import money, to_decimal
from src.db import get_session
from src.models.trading import (
    DailyLogStatus,
    OrderAction,
    OrderRecord,
    OrderStatus,
    SellReason,
    Strategy,
    StrategyDailyLog,
)
from src.repositories import daily_log_repo, order_record_repo, position_repo
from src.service.chip_tracker import fetch_signals_with_retry
from src.service.trader import get_all_orders, get_quote, place_buy_order, place_sell_order

logger = logging.getLogger(__name__)

# 台股交易成本（估算）：手續費 0.1425%（最低 NT$20）、賣出證交稅 0.3%
FEE_RATE = Decimal("0.001425")
MIN_FEE = Decimal("20")
SELL_TAX_RATE = Decimal("0.003")

# 單筆買入資金低於此值就放棄（買不到最小單位）
MIN_BUY_FUND = Decimal("1000")

_SIGNAL_BACK_TEST_PERIOD = 4


# ---------------------------------------------------------------------------
# 15:30 — signal generation for the NEXT trading day
# ---------------------------------------------------------------------------

async def generate_daily_signals(strategy: Strategy) -> dict:
    """Compute tomorrow's signals and create its daily log (SIGNAL_GENERATED).
    Also refreshes each position's price / trailing stop from the snapshot."""
    target_date = date.fromisoformat(get_action_date())

    async with get_session() as session:
        existing = await daily_log_repo.get_log_by_date(session, strategy.id, target_date)
        if existing is not None:
            logger.info(f"[Signal] Log for {strategy.id} @ {target_date} already exists; skipping")
            return {"strategy_id": strategy.id, "status": "already_generated"}

        baseline = await daily_log_repo.get_latest_ended_log(session, strategy.id)
        balance = baseline.available_balance if baseline else to_decimal(strategy.initial_capital)
        equity = baseline.total_equity if baseline else to_decimal(strategy.initial_capital)

    settings = {
        "volume_multiplier": strategy.volume_multiplier,
        "concentration_slope": strategy.concentration_slope,
        "back_test_period": _SIGNAL_BACK_TEST_PERIOD,
    }
    # fetch_signals_with_retry blocks (sleeps between retries) — keep it off the loop
    buy_list, sell_hint, snapshot, error = await asyncio.to_thread(
        fetch_signals_with_retry, settings
    )
    if error:
        logger.error(f"[Signal] chip-tracker failed for {strategy.id}: {error}")

    atr_multiplier = to_decimal(strategy.atr_multiplier)

    async with get_session() as session:
        # 訊號計算耗時數分鐘（重試間隔最長 5 分鐘），開頭那次檢查早已過期 —
        # 併發的另一次執行（ofelia 觸發 + 手動強制執行、或建立策略的背景任務）
        # 可能已經建好這天的 Log，插入前再確認一次。
        existing = await daily_log_repo.get_log_by_date(session, strategy.id, target_date)
        if existing is not None:
            logger.info(f"[Signal] Log for {strategy.id} @ {target_date} created concurrently; skipping")
            return {"strategy_id": strategy.id, "status": "already_generated"}

        # 1. 更新持倉的現價與移動停損（停損只會往上移）
        positions = await position_repo.list_positions(session, strategy.id)
        for position in positions:
            info = snapshot.get(position.symbol)
            if not info or info.get("p") is None or info.get("atr") is None:
                continue
            price = to_decimal(info["p"])
            atr = to_decimal(info["atr"])
            new_stop = money(max(position.highest_price, price) - atr * atr_multiplier)
            await position_repo.update_market_data(session, position, price, new_stop)

        # 2. 建立明日的 Daily Log（快照為不可變的除錯資料）
        buy_signals = []
        for symbol in buy_list:
            info = snapshot.get(symbol) or {}
            buy_signals.append(
                {"symbol": symbol, "price": info.get("p"), "atr": info.get("atr")}
            )

        holdings = [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "average_cost": float(p.average_cost),
                "current_price": float(p.current_price),
                "highest_price": float(p.highest_price),
                "trailing_stop_price": float(p.trailing_stop_price),
            }
            for p in positions
        ]

        log = StrategyDailyLog(
            strategy_id=strategy.id,
            status=DailyLogStatus.SIGNAL_GENERATED,
            record_date=target_date,
            total_equity=equity,
            available_balance=balance,
            holdings_snapshot=holdings,
            buy_signals_snapshot=buy_signals,
            sell_signals_snapshot=[{"symbol": s} for s in sell_hint],
            errors=[f"signal fetch failed: {error}"] if error else [],
        )
        try:
            await daily_log_repo.create_log(session, log)
            await session.commit()
        except IntegrityError:
            # 兩次執行同時通過上面的檢查 — 唯一約束是最終仲裁者，輸的一方
            # 視同已產生（贏的那次已做了等價的停損更新與 Log）。
            await session.rollback()
            logger.info(f"[Signal] Log for {strategy.id} @ {target_date} lost insert race; skipping")
            return {"strategy_id": strategy.id, "status": "already_generated"}

    logger.info(
        f"[Signal] {strategy.id} @ {target_date}: {len(buy_list)} buy signal(s), "
        f"{len(sell_hint)} sell hint(s)"
    )
    return {
        "strategy_id": strategy.id,
        "status": "generated" if not error else "generated_with_error",
        "record_date": target_date.isoformat(),
        "buy_signals": len(buy_list),
        "sell_hints": len(sell_hint),
    }


# ---------------------------------------------------------------------------
# 09:00-13:30 — order execution for today's log
# ---------------------------------------------------------------------------

async def execute_daily_strategy(strategy: Strategy) -> dict:
    """Place trailing-stop sells then signal buys for today's log."""
    today = get_date_tw()

    async with get_session() as session:
        log = await daily_log_repo.get_log_by_date(session, strategy.id, today)
        if log is None:
            logger.warning(f"[Execute] No daily log for {strategy.id} @ {today}")
            return {"strategy_id": strategy.id, "status": "no_log"}
        if log.status != DailyLogStatus.SIGNAL_GENERATED:
            logger.info(f"[Execute] {strategy.id} log already {log.status}; skipping")
            return {"strategy_id": strategy.id, "status": f"skipped ({log.status})"}

        log.status = DailyLogStatus.EXECUTING
        log.execute_at = get_datetime_tw()
        session.add(log)

        log_id = log.id
        available_balance = log.available_balance
        buy_signals = list(log.buy_signals_snapshot or [])

        positions = await position_repo.list_positions(session, strategy.id)
        held_symbols = {p.symbol for p in positions}
        stop_candidates = [
            (p.symbol, p.quantity, p.trailing_stop_price)
            for p in positions
            if p.quantity > 0 and p.trailing_stop_price > 0
        ]

        # 今日已有掛單/成交的標的不能重複下單（FAILED/CANCELLED 不擋重試）
        orders_today = await order_record_repo.list_orders_on_date(session, strategy.id, today)
        blocked_symbols = {
            o.symbol
            for o in orders_today
            if o.status not in (OrderStatus.FAILED, OrderStatus.CANCELLED)
        }
        await session.commit()

    order_ids: list[int] = []
    errors: list[str] = []
    sells_placed = 0
    buys_placed = 0

    # --- 1. 停損賣出優先（保護資本） ---
    for symbol, quantity, stop_price in stop_candidates:
        if symbol in blocked_symbols:
            logger.info(f"[Execute] Skip SELL {symbol}: already traded today")
            continue
        quote = await get_quote(symbol)
        if quote is None:
            errors.append(f"quote unavailable for {symbol}; stop check skipped")
            continue
        if quote < stop_price:
            ids = await place_sell_order(symbol, quantity, strategy.id, SellReason.TRAILING_STOP)
            if ids:
                order_ids.extend(ids)
                sells_placed += 1
                blocked_symbols.add(symbol)
            else:
                errors.append(f"sell order failed for {symbol}")

    # --- 2. 依剩餘資金分份買入新訊號 ---
    remaining_cash = available_balance
    slot_fund = money(available_balance / strategy.position_slots)

    for signal in buy_signals:
        symbol = signal.get("symbol")
        if not symbol or symbol in held_symbols or symbol in blocked_symbols:
            continue
        fund = min(slot_fund, remaining_cash)
        if fund < MIN_BUY_FUND:
            logger.info(f"[Execute] Skip BUY {symbol}: fund {fund} below minimum")
            continue
        order_id = await place_buy_order(symbol, fund, strategy.id)
        if order_id is not None:
            order_ids.append(order_id)
            buys_placed += 1
            blocked_symbols.add(symbol)
            remaining_cash = money(remaining_cash - fund)
        else:
            errors.append(f"buy order failed for {symbol}")

    if errors:
        async with get_session() as session:
            log = await daily_log_repo.get_log(session, log_id)
            if log:
                for message in errors:
                    await daily_log_repo.append_error(session, log, message)
            await session.commit()

    if order_ids:
        logger.info(f"[Execute] {strategy.id}: polling {len(order_ids)} order(s) in background")
        asyncio.create_task(poll_order_status(strategy.id, log_id, order_ids))

    return {
        "strategy_id": strategy.id,
        "status": "executed",
        "buys_placed": buys_placed,
        "sells_placed": sells_placed,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Fill polling — updates order_record + position + log balance atomically
# ---------------------------------------------------------------------------

async def _apply_broker_state(
    session, order: OrderRecord, broker, log: StrategyDailyLog
) -> None:
    """Apply the broker-reported state onto one order: incremental fill deltas
    move the position and the day's balance; totals (fee/tax/pnl) are recomputed
    from the cumulative filled quantity so partial fills never double-count."""
    delta = broker.filled_qty - order.filled_quantity
    price = broker.avg_price

    if delta > 0 and price > 0:
        gross_delta = money(price * delta)
        new_total_fee = money(max(price * broker.filled_qty * FEE_RATE, MIN_FEE))
        fee_delta = new_total_fee - order.fee

        if order.action == OrderAction.BUY:
            await position_repo.apply_buy_fill(
                session, order.strategy_id, order.symbol, delta, price
            )
            log.available_balance = money(log.available_balance - gross_delta - fee_delta)
        else:
            average_cost = await position_repo.apply_sell_fill(
                session, order.strategy_id, order.symbol, delta
            )
            new_total_tax = money(price * broker.filled_qty * SELL_TAX_RATE)
            tax_delta = new_total_tax - order.tax
            log.available_balance = money(
                log.available_balance + gross_delta - fee_delta - tax_delta
            )
            if average_cost is not None:
                order.realized_pnl = money(
                    order.realized_pnl + (price - average_cost) * delta - fee_delta - tax_delta
                )
                cost_basis = average_cost * broker.filled_qty
                order.return_rate = (
                    float(order.realized_pnl / cost_basis * 100) if cost_basis else 0.0
                )
            order.tax = new_total_tax

        order.fee = new_total_fee
        order.filled_quantity = broker.filled_qty
        order.filled_price = price
        session.add(log)

    if broker.is_failed:
        order.status = OrderStatus.FAILED
        order.error_msg = broker.error_msg
    elif broker.is_filled:
        order.status = OrderStatus.FILLED
    elif 0 < broker.filled_qty < broker.total_qty:
        order.status = OrderStatus.PARTIAL

    order.update_at = get_datetime_tw()
    session.add(order)


async def poll_order_status(strategy_id: str, log_id: int, order_ids: list[int]) -> None:
    """Background task: poll broker order state until every order reaches a
    terminal status or the attempt budget runs out (then mark TIMEOUT)."""
    max_attempts = 15
    attempt = 0
    wait_time = 5.0
    pending_ids = set(order_ids)

    while pending_ids and attempt < max_attempts:
        logger.info(f"[Poll] Attempt {attempt + 1}: waiting {wait_time}s for {len(pending_ids)} order(s)")
        await asyncio.sleep(wait_time)
        wait_time = min(wait_time * 2, 300.0)
        attempt += 1

        try:
            broker_orders = await get_all_orders()

            async with get_session() as session:
                log = await daily_log_repo.get_log(session, log_id)
                orders = await order_record_repo.get_orders_by_ids(session, list(pending_ids))

                for order in orders:
                    broker = broker_orders.get(order.broker_order_id or "")
                    if broker is None:
                        continue
                    await _apply_broker_state(session, order, broker, log)
                    if order.status in (
                        OrderStatus.FILLED,
                        OrderStatus.FAILED,
                        OrderStatus.CANCELLED,
                    ):
                        pending_ids.discard(order.id)
                        logger.info(f"[Poll] Order {order.broker_order_id} → {order.status}")

                await session.commit()
        except Exception as exc:
            logger.error(f"[Poll] Error checking orders: {exc}")

    if pending_ids:
        async with get_session() as session:
            orders = await order_record_repo.get_orders_by_ids(session, list(pending_ids))
            for order in orders:
                logger.warning(f"[Poll] Order record {order.id} TIMEOUT")
                await order_record_repo.update_order(
                    session, order, status=OrderStatus.TIMEOUT,
                    error_msg="Wait for fill timed out",
                )
            await session.commit()


# ---------------------------------------------------------------------------
# 15:00 — daily settlement
# ---------------------------------------------------------------------------

async def finalize_daily_settlement(strategy: Strategy) -> dict:
    """Mark positions to market and settle today's equity / daily PnL."""
    today = get_date_tw()

    async with get_session() as session:
        log = await daily_log_repo.get_log_by_date(session, strategy.id, today)
        if log is None:
            logger.warning(f"[Settle] No daily log for {strategy.id} @ {today}")
            return {"strategy_id": strategy.id, "status": "no_log"}
        if log.status == DailyLogStatus.ENDED:
            return {"strategy_id": strategy.id, "status": "already_settled"}

        log.status = DailyLogStatus.FINALIZING
        session.add(log)
        await session.flush()

        # 前一日 ENDED 的帳是今日損益的基準（今日這筆還在 FINALIZING，不會撈到自己）
        previous = await daily_log_repo.get_latest_ended_log(session, strategy.id)

        market_value = Decimal("0")
        positions = await position_repo.list_positions(session, strategy.id)
        for position in positions:
            quote = await get_quote(position.symbol)
            if quote is not None:
                await position_repo.update_market_data(session, position, quote)
            else:
                await daily_log_repo.append_error(
                    session, log, f"settlement quote unavailable for {position.symbol}"
                )
            market_value += position.current_price * position.quantity

        log.total_equity = money(log.available_balance + market_value)
        baseline_equity = previous.total_equity if previous else to_decimal(strategy.initial_capital)
        log.daily_pnl = money(log.total_equity - baseline_equity)
        log.status = DailyLogStatus.ENDED
        session.add(log)
        await session.commit()

        logger.info(
            f"[Settle] {strategy.id} @ {today}: equity={log.total_equity}, pnl={log.daily_pnl}"
        )
        return {
            "strategy_id": strategy.id,
            "status": "settled",
            "total_equity": float(log.total_equity),
            "daily_pnl": float(log.daily_pnl),
        }
