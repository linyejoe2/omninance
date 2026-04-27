from src.db import get_strategy, get_last_daily_log, StrategyDailyLog, save_strategy_daily_log
import logging
from src.core.date_time_util import get_datetime_tw
import httpx
import asyncio
from src.service.trader import get_all_orders, place_buy_order, get_quote, place_sell_order
from src.db import get_trade_records_by_ids, update_trade_record, get_last_unexecuted_daily_log, BuyObj, update_buy_obj, add_sell_obj, SellObj, update_sell_obj, engine, ensure_pydantic, Holding
from sqlmodel import Session, select
from typing import Dict


logger = logging.getLogger(__name__)

def create_pending_signal_log(strategy_id: str, buy_symbol_list: list[str], snapshot: dict):
    # 1. 獲取策略設定 (包含初始資金與 ATR 乘數)
    strategy = get_strategy(strategy_id)
    if not strategy:
        logger.error(f"Strategy {strategy_id} not found.")
        return None
    
    # 2. 抓取「最新一筆」紀錄, 即今天早上剛執行完的紀錄
    prev_log = get_last_daily_log(strategy_id)

    # --- 繼承資產邏輯 ---
    if prev_log:
        # 已經有執行過的紀錄，繼承最後的結果
        current_equity = prev_log.total_equity
        current_balance = prev_log.available_balance
        old_holdings = prev_log.holdings_snapshot
    else:
        # 第一筆紀錄：從 Strategy 設定抓取初始值
        logger.info(f"First log for strategy {strategy_id}. Using initial capital: {strategy.initial_capital}")
        current_equity = strategy.initial_capital
        current_balance = strategy.initial_capital
        old_holdings = []

    # 3. 更新持倉快照 (更新現價、最高價、停損價)
    new_holdings = []
    for h in old_holdings:
        symbol = h["symbol"]
        api_data = snapshot.get(symbol) or snapshot.get(f"{symbol}.TW") # 假設 API key 格式
        
        if api_data:
            new_price = api_data["p"]
            atr = api_data["atr"]
            
            # 更新最高價
            h["highest_price"] = max(h.get("highest_price", 0), new_price)
            h["current_price"] = new_price

            # --- 移動停損計算 ---
            # 使用 StrategyBase 裡的 atr_multiplier
            stop_distance = atr * strategy.atr_multiplier
            new_stop_price = h["highest_price"] - stop_distance
            
            # 停損價只能往上移，不能往下移 (移動停損原則)
            h["stop_price"] = max(h.get("stop_price", 0), new_stop_price)
        new_holdings.append(h)
        
    # 3-1. 初始化 buy list
    buy_list = [BuyObj(symbol=s) for s in buy_symbol_list]

    # 4. 寫入新的 Daily Log (狀態 2：Pending)
    new_log = StrategyDailyLog(
        strategy_id=strategy_id,
        compute_at=get_datetime_tw(), # 盤後計算時間
        execute_at=None,           # 尚未執行
        total_equity=current_equity,
        available_balance=current_balance,
        holdings_snapshot=new_holdings,
        buy_list=buy_list,
        sell_list=[]               # 執行時才會填入
    )
    return save_strategy_daily_log(new_log)

async def execute_strategy(
    strategy_id: str,
):
    """Compute signals via chip-tracker then place buy orders via omnitrader."""
    
    log = get_last_unexecuted_daily_log(strategy_id)
    if not log:
        logger.error("No pending signal log found for execution!")
        return
    
    strategy = get_strategy(strategy_id)
    if not strategy:
        logger.error(f"Strategy {strategy_id} not found.")
        return None
    
    partition = strategy.partition
    run_date = get_datetime_tw().isoformat()
    available_balance = log.available_balance
    today_holdings = log.holdings_snapshot
    buy_list = log.buy_list
    

    # 資金分配：每份 = 可用餘額 ÷ partition；已持有的跳過
    buy_plans: Dict[str, float] = {}
    temp_cash = available_balance
    for symbol in buy_list:
        if symbol in today_holdings:
            continue
        fund = temp_cash * (1 / partition)
        if fund < 1000:
            continue
        buy_plans[symbol] = fund
        temp_cash -= fund

    if buy_plans:
        tasks = [place_buy_order(s, f, strategy_id) for s, f in buy_plans.items()]
        record_ids = await asyncio.gather(*tasks)

        successful_ids = [rid for rid in record_ids if rid is not None]

        if successful_ids:
            # Scheduler 情境：手動丟進原生 asyncio event loop
            # 這樣不會阻塞主排程，且能確保 polling 繼續執行
            logger.info(f"Triggering background polling for {len(successful_ids)} buy orders.")
            asyncio.create_task(poll_order_status(log.id, strategy_id, successful_ids))
    
    sell_ids: list[int] = []
    for symbol in today_holdings:
        quote = await get_quote(symbol.symbol)
        if quote and quote < symbol.stop_price:
            # 觸發移動停損
            sell_ids.append(await place_sell_order(symbol.symbol, symbol.quantity, strategy_id))
            
            add_sell_obj(log.id, SellObj(symbol=symbol.symbol, price=quote, quantity=symbol.quantity, reason="ATR_STOP"))
        
        if sell_ids:
            # Scheduler 情境：手動丟進原生 asyncio event loop
            # 這樣不會阻塞主排程，且能確保 polling 繼續執行
            logger.info(f"Triggering background polling for {len(sell_ids)} sell orders.")
            asyncio.create_task(poll_order_status(log.id, strategy_id, sell_ids))
    
    return 

async def poll_order_status(log_id: int, strategy_id: str, record_ids: list[int]) -> None:
    """
    背景任務：輪詢委託狀態，直到全部 FILLED / FAILED / TIMEOUT。
    """
    max_attempts = 15
    attempt = 0
    pending_ids = set(record_ids)
    wait_time = 5.0

    while pending_ids and attempt < max_attempts:
        # 1. 執行等待
        logger.info(f"[Polling] Attempt {attempt+1}, waiting {wait_time}s for {len(pending_ids)} orders...")
        await asyncio.sleep(wait_time)
        
        wait_time = min(wait_time * 2, 300.0)
        attempt += 1

        try:
            api_orders = await get_all_orders()

            records = get_trade_records_by_ids(list(pending_ids))

            for rec in records:
                ord_no = rec.order_id
                if not ord_no or ord_no not in api_orders:
                    continue

                order_info = api_orders[ord_no]
                filled = order_info.get("mat_qty_share", 0)
                total  = order_info.get("org_qty_share", 0)
                price = float(order_info.get("avg_price", 0))
                
                # --- 1. 根據 Action 執行不同的 Side Effect (更新 Daily Log) ---
                if rec.action == "BUY":
                    # 買單：更新 buy_list 狀態
                    update_buy_obj(log_id, BuyObj(
                        symbol=rec.symbol, 
                        bought=(filled >= total and total > 0), # 是否完全買入
                        price=price, 
                        quantity=filled
                    ))
                
                elif rec.action == "SELL":
                    # 賣單：只有在有成交時，才更新或新增到 sell_list
                    if filled > 0:
                        update_sell_obj(log_id, SellObj(
                            symbol=rec.symbol,
                            price=price,
                            quantity=filled,
                            reason="STRATEGY_EXIT" # 或是根據訊號來源決定
                        ))

                # 3. 判斷成交狀態
                # 完全成交
                if filled >= total and total > 0:
                    update_trade_record(
                        rec.id,
                        status="FILLED",
                        filled_qty=filled,
                        result=f"Fully filled at {get_datetime_tw().isoformat()}"
                    )
                    pending_ids.discard(rec.id)
                elif order_info.get("err_code", "00000000") != "00000000":
                    update_trade_record(
                        rec.id,
                        status="FAILED",
                        error=order_info.get("err_msg"),
                    )
                    pending_ids.discard(rec.id)
                    logger.warning(f"[Poll] Order {ord_no} FAILED: {order_info.get('err_msg')}")

        except Exception as exc:
            logger.error("[Poll] Error checking orders: %s", exc)

    for remaining_id in pending_ids:
        logger.warning(f"[Poll] Order record {remaining_id} TIMEOUT.")
        update_trade_record(remaining_id, status="TIMEOUT", error="Wait for filled timeout")
        
async def finalize_daily_settlement(strategy_id: str, current_log_id: int):
    with Session(engine) as session:
        # 1. 取得當前日誌與昨日日誌
        log = session.get(StrategyDailyLog, current_log_id)
        # 抓取該策略倒數第二筆紀錄 (昨日結算)
        yesterday_log = session.exec(
            select(StrategyDailyLog)
            .where(StrategyDailyLog.strategy_id == strategy_id)
            .where(StrategyDailyLog.id < current_log_id)
            .order_by(StrategyDailyLog.id.desc())
        ).first()

        if not log:
            return

        # --- A. 更新可用餘額 (Available Balance) ---
        # 根據你提供的公式：餘額 = 舊餘額 - 買入總額 + 賣出總額
        # 注意：此處需計算手續費與交易稅才夠精確
        total_buy_cost = sum(b["price"] * b["quantity"] for b in log.buy_list if b.get("bought"))
        total_sell_proceeds = sum(s["price"] * s["quantity"] for s in log.sell_list if s.get("sold"))
        
        # 假設 log.available_balance 初始值是從昨日繼承過來的預算
        log.available_balance = log.available_balance - total_buy_cost + total_sell_proceeds

        # --- B. 更新持倉快照 (Holdings Snapshot) ---
        # 邏輯：原本持有 - 今日賣出 + 今日買入
        new_holdings_map = {h["symbol"]: ensure_pydantic(h, Holding) for h in log.holdings_snapshot}

        # 1. 移除已賣出的 (或減少數量)
        for s in log.sell_list:
            if s.get("sold") and s["symbol"] in new_holdings_map:
                if s["quantity"] == new_holdings_map[s["symbol"]].quantity:
                    del new_holdings_map[s["symbol"]]
            else:
                new_holdings_map[s["symbol"]].quantity -= s["quantity"]

        # 2. 加入新買入的
        for b in log.buy_list:
            if b.get("bought"):
                symbol = b["symbol"]
                new_holdings_map[symbol] = Holding(
                    symbol=symbol,
                    quantity=b["quantity"],
                    cost=b["price"],
                    current_price=b["price"], # 初始現價等於成交價
                    highest_price=b["price"],
                    stop_price=0.0 # 待後續移動停損邏輯計算
                )

        # 3. 更新所有持倉的最新市價並計算總市值
        total_market_value = 0.0
        final_holdings = []
        for symbol, h in new_holdings_map.items():
            quote = await get_quote(symbol) # 取得盤後收盤價
            if quote:
                h.current_price = quote
                h.highest_price = max(h.highest_price, quote)
            
            total_market_value += (h.current_price * h.quantity)
            final_holdings.append(h.model_dump())

        log.holdings_snapshot = final_holdings

        # --- C. 更新資產總值與盈虧 ---
        log.total_equity = log.available_balance + total_market_value
        
        if yesterday_log:
            # 絕對金額損益
            log.daily_pnl = log.total_equity - yesterday_log.total_equity
        else:
            log.daily_pnl = 0.0

        # --- D. 存檔 ---
        session.add(log)
        session.commit()
        logger.info(f"Settlement Done: Equity={log.total_equity}, PnL={log.daily_pnl}")