from fastapi import APIRouter
from pydantic import BaseModel

from esun_trade.constant import Action, APCode, BSFlag, PriceFlag, Trade
from esun_trade.order import OrderObject
from src.sdk_client import get_sdk

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
