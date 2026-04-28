from fastapi import APIRouter

from src.sdk_client import get_sdk, get_last_price, get_quote

router = APIRouter(prefix="/api/market", tags=["market"])

@router.get("/quote/{symbol}")
def _(symbol: str):
    return get_last_price(symbol)

@router.get("/quote-all/{symbol}/{type_}")
def _(symbol: str, type_: str):
    return get_quote(symbol, type_)