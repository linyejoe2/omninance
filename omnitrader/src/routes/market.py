from fastapi import APIRouter

from src.sdk_client import get_sdk, get_last_price

router = APIRouter(prefix="/api/market", tags=["market"])

@router.get("/quote/{symbol}")
def _(symbol: str):
    return get_last_price(symbol)