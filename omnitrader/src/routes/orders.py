from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

from esun_trade.constant import Action, APCode, BSFlag, PriceFlag, Trade
from esun_trade.order import OrderObject
from src.sdk_client import get_sdk, get_last_price, get_symbol_position
from src.util import get_tick_size

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])


class PlaceOrderRequest(BaseModel):
    stock_no: str
    buy_sell: str               # "B" | "S"
    price: float | None = None  # None when price_flag is not Limit
    quantity: int
    ap_code: str = APCode.Common
    bs_flag: str = BSFlag.ROD
    price_flag: str = PriceFlag.Limit
    trade: str = Trade.Cash
    user_def: str = ""

class AggressiveOrderRequest(BaseModel):
    stock_no: str = Field(..., description="股票代號，例如 '2330'")
    
    tick: int = Field(
        default=2, 
        ge=0, 
        le=10, 
        description="在現價之上加幾檔（Tick）委託。0 代表準用現價，上限建議設為 10 檔。"
    )
    quantity: Optional[int] = Field(
        None, 
        ge=1, 
        description="欲買入的張數。若提供此值，將忽略 fund 參數。"
    )
    fund: Optional[float] = Field(
        None, 
        ge=1000, 
        description="最大買入總金額限制（台幣）。當 quantity 為 None 時，會根據此預算自動計算張數。"
    )
    liquidation: Optional[bool] = Field(
        None, 
        description="清倉，只有在賣出時且沒有指定 quantity 時有效"
    )
    user_def: Optional[str] = Field(
        None, 
        max_length=20, 
        description="自定義標記，用於回頭追蹤訂單來源。"
    )

class CancelOrderRequest(BaseModel):
    order_result: dict
    cel_qty_share: int | None = None  # omit to cancel all


class ModifyPriceRequest(BaseModel):
    order_result: dict
    price: float
    price_flag: str = PriceFlag.Limit


@router.get("")
def get_orders():
    """Get all today's order results."""
    return get_sdk().get_order_results()


@router.post("/aggressive-limit-order")
def buy_at_best_price(req: AggressiveOrderRequest):
    # 1. 取得即時報價 (假設你的 SDK 有提供 get_snapshot)
    current_price = get_last_price(req.stock_no)  # 取得現價
    
    if not current_price or current_price <= 0:
        raise HTTPException(status_code=400, detail="無法取得即時報價")

    # 2. 計算偏移後的委託價 (現價 + n 個 Tick)
    tick_size = get_tick_size(current_price)
    target_price = current_price + (req.tick * tick_size)
    
    # 修正價格精度，避免 API 報錯 (例如 100 元以上必須是 0.5 的倍數)
    target_price = round(target_price, 2)
    
    # 3. 如果沒給數量，改用資金上限 (fund) 計算最大可買張數
    quantity = req.quantity
    if not quantity or quantity <= 0:
        if not req.fund or req.fund <= 0:
            raise HTTPException(status_code=400, detail="必須提供 quantity 或 fund")
        
        # 計算公式：預算 / (委託價 * 1000 股) -> 取整數
        # 這裡建議保留 0.2% 左右的手續費緩衝
        quantity = int(req.fund / (target_price * 1.002))
        
        if quantity < 1000:
            # return {"status": "skipped", "reason": "資金不足以購買一張", "calc_price": target_price}
            # 購買零股
            # 4. 建構委託物件 (強制使用限價單 PriceFlag.Limit)
            order = OrderObject(
                buy_sell=Action.Buy,
                price=target_price,
                stock_no=req.stock_no,
                quantity=quantity,
                ap_code=APCode.IntradayOdd,     # 盤中整股
                bs_flag=BSFlag.ROD,        # 當日有效
                price_flag=PriceFlag.Limit, # 限價單
                trade=Trade.Cash,
                user_def=req.user_def,
            )
            
        else:
            # 4. 建構委託物件 (強制使用限價單 PriceFlag.Limit)
            order = OrderObject(
                buy_sell=Action.Buy,
                price=target_price,
                stock_no=req.stock_no,
                quantity=int(quantity / 1000),
                ap_code=APCode.Common,     # 盤中整股
                bs_flag=BSFlag.ROD,        # 當日有效
                price_flag=PriceFlag.Limit, # 限價單
                trade=Trade.Cash,
                user_def=req.user_def,
            )
            
    # 5. 送出交易
    result = get_sdk().place_order(order)
    
    s = {
        "status": "success",
        "order_id": result.get("ord_no"),
        "executed_price": target_price,
        "quantity": quantity,
        "detail": result
    }
    
    logger.info(s)
    
    return s

@router.post("/sell-at-best-price")
def sell_at_best_price(req: AggressiveOrderRequest):
    # 1. 取得即時報價
    current_price = get_last_price(req.stock_no)
    
    if not current_price or current_price <= 0:
        raise HTTPException(status_code=400, detail="無法取得即時報價")

    # 2. 計算偏移後的委託價 (現價 - n 個 Tick) 
    # 買入是加，賣出則是減，確保直接撞買盤 (Bid)
    tick_size = get_tick_size(current_price)
    target_price = current_price - (req.tick * tick_size)
    
    # 修正價格精度，避免 API 報錯 (例如 100 元以上必須是 0.5 的倍數)
    target_price = round(target_price, 2)

    # 3. 處理賣出數量
    quantity = req.quantity
    
    # 如果沒給數量且 liquidation=true，則查詢庫存並全部賣出
    if (not quantity or quantity <= 0) and getattr(req, 'liquidation', False):
        # 假設你的 SDK 有 get_position 或類似方法
        pos = get_symbol_position(req.stock_no)
        
        if not pos or pos <= 0:
            return {"status": "skipped", "reason": "持有庫存為 0，無需清倉"}
        
        quantity = pos # 這裡的 quantity 通常是「股」
        logger.info(f"[Liquidation] 準備清倉 {req.stock_no} 數量: {quantity}")

    if not quantity or quantity <= 0:
        raise HTTPException(status_code=400, detail="必須提供 quantity 或開啟 liquidation 模式")

    # --- 2. 核心邏輯：拆分整股與零股 ---
    common_qty = quantity // 1000  # 整股張數 (張)
    odd_qty = quantity % 1000      # 零股股數 (股)
    
    orders_to_place = []
    
    # 準備整股訂單
    if common_qty > 0:
        orders_to_place.append({
            "type": "COMMON",
            "order": OrderObject(
                buy_sell=Action.Sell,
                price=target_price,
                stock_no=req.stock_no,
                quantity=common_qty,
                ap_code=APCode.Common,
                bs_flag=BSFlag.ROD,
                price_flag=PriceFlag.Limit,
                trade=Trade.Cash,
                user_def=f"{req.user_def}-C"
            )
        })
        
    # 準備零股訂單
    if odd_qty > 0:
        orders_to_place.append({
            "type": "ODD",
            "order": OrderObject(
                buy_sell=Action.Sell,
                price=target_price,
                stock_no=req.stock_no,
                quantity=odd_qty,
                ap_code=APCode.IntradayOdd,
                bs_flag=BSFlag.ROD,
                price_flag=PriceFlag.Limit,
                trade=Trade.Cash,
                user_def=f"{req.user_def}-O"
            )
        })

    # --- 3. 執行並整合結果 ---
    results = []
    success_count = 0
    
    for item in orders_to_place:
        try:
            res = get_sdk().place_order(item["order"])
            results.append({
                "type": item["type"],
                "status": "success",
                "order_id": res.get("ord_no"),
                "qty": item["order"].quantity
            })
            success_count += 1
        except Exception as e:
            results.append({
                "type": item["type"],
                "status": "error",
                "error": str(e)
            })

    # --- 4. 最終回傳 ---
    final_status = "success" if success_count == len(orders_to_place) else "partial_success"
    if success_count == 0: final_status = "failed"

    return {
        "status": final_status,
        "stock_no": req.stock_no,
        "target_price": target_price,
        "total_requested_qty": quantity,
        "order_details": results
    }

@router.post("")
def place_order(req: PlaceOrderRequest):
    """Place a new order."""
    price = req.price if PriceFlag(req.price_flag) == PriceFlag.Limit else None
    order = OrderObject(
        buy_sell=Action(req.buy_sell),
        price=price,
        stock_no=req.stock_no,
        quantity=req.quantity,
        ap_code=APCode(req.ap_code),
        bs_flag=BSFlag(req.bs_flag),
        price_flag=PriceFlag(req.price_flag),
        trade=Trade(req.trade),
        user_def=req.user_def,
    )
    return get_sdk().place_order(order)


@router.post("/cancel")
def cancel_order(req: CancelOrderRequest):
    """Cancel an order (all lots, or a partial quantity via cel_qty_share)."""
    sdk = get_sdk()
    if req.cel_qty_share is not None:
        return sdk.cancel_order(req.order_result, cel_qty_share=req.cel_qty_share)
    return sdk.cancel_order(req.order_result)


@router.post("/modify-price")
def modify_price(req: ModifyPriceRequest):
    """Modify the limit price of an outstanding order."""
    return get_sdk().modify_price(
        req.order_result, req.price, PriceFlag(req.price_flag)
    )

