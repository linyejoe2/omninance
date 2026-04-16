from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from esun_trade.constant import Action, APCode, BSFlag, PriceFlag, Trade
from esun_trade.order import OrderObject
from src.sdk_client import get_sdk
from src.util import get_tick_size

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
    user_def: Optional[str] = Field(
        None, 
        max_length=20, 
        description="自定義標記，用於回頭追蹤訂單來源。"
    )

class CancelOrderRequest(BaseModel):
    order_result: dict
    cel_qty: int | None = None  # omit to cancel all


class ModifyPriceRequest(BaseModel):
    order_result: dict
    price: float
    price_flag: str = PriceFlag.Limit


@router.get("")
def get_orders():
    """Get all today's order results."""
    return get_sdk().get_order_results()


@router.post("aggressive-limit-order")
def buy_at_best_price(req: AggressiveOrderRequest):
    # 1. 取得即時報價 (假設你的 SDK 有提供 get_snapshot)
    snapshot = get_sdk().get_snapshot(req.stock_no)
    current_price = snapshot.get("p")  # 取得現價
    
    if not current_price or current_price <= 0:
        raise HTTPException(status_code=400, detail="無法取得即時報價")

    # 2. 計算偏移後的委託價 (現價 + n 個 Tick)
    tick_size = get_tick_size(current_price)
    target_price = current_price + (req.tick * tick_size)
    
    # 3. 如果沒給數量，改用資金上限 (fund) 計算最大可買張數
    quantity = req.quantity
    if not quantity or quantity <= 0:
        if not req.fund or req.fund <= 0:
            raise HTTPException(status_code=400, detail="必須提供 quantity 或 fund")
        
        # 計算公式：預算 / (委託價 * 1000 股) -> 取整數
        # 這裡建議保留 0.2% 左右的手續費緩衝
        quantity = int(req.fund / (target_price * 1000 * 1.002))
        
        if quantity < 1:
            return {"status": "skipped", "reason": "資金不足以購買一張", "calc_price": target_price}

    # 4. 建構委託物件 (強制使用限價單 PriceFlag.Limit)
    order = OrderObject(
        buy_sell=Action.Buy,
        price=target_price,
        stock_no=req.stock_no,
        quantity=quantity,
        ap_code=APCode.Common,     # 盤中整股
        bs_flag=BSFlag.ROD,        # 當日有效
        price_flag=PriceFlag.Limit, # 限價單
        trade=Trade.Cash,
        user_def=req.user_def,
    )
    
    # 5. 送出交易
    result = get_sdk().place_order(order)
    
    return {
        "status": "success",
        "order_id": result.get("order_id"),
        "executed_price": target_price,
        "quantity": quantity,
        "detail": result
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
    """Cancel an order (all lots, or a partial quantity via cel_qty)."""
    sdk = get_sdk()
    if req.cel_qty is not None:
        return sdk.cancel_order(req.order_result, cel_qty=req.cel_qty)
    return sdk.cancel_order(req.order_result)


@router.post("/modify-price")
def modify_price(req: ModifyPriceRequest):
    """Modify the limit price of an outstanding order."""
    return get_sdk().modify_price(
        req.order_result, req.price, PriceFlag(req.price_flag)
    )
