from fastapi import APIRouter

from src.sdk_client import get_sdk, get_symbol_position

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/inventories")
def get_inventories():
    """Get current stock holdings."""
    return get_sdk().get_inventories()


@router.get("/balance")
def get_balance():
    """Get account cash balance."""
    return get_sdk().get_balance()


@router.get("/trade-status")
def get_trade_status():
    """Get trading account status."""
    return get_sdk().get_trade_status()


@router.get("/market-status")
def get_market_status():
    """Get market open/close status."""
    return get_sdk().get_market_status()


@router.get("/settlements")
def get_settlements():
    """Get settlement records."""
    return get_sdk().get_settlements()


@router.get("/transactions")
def get_transactions(query_range: str = "0"):
    """Get matched transaction records. query_range: '0'=today, '3'=3 days."""
    return get_sdk().get_transactions(query_range)


@router.get("/cert-info")
def get_cert_info():
    """Get certificate information."""
    return get_sdk().certinfo()


@router.get("/key-info")
def get_key_info():
    """Get API key information."""
    return get_sdk().get_key_info()

@router.get("/get-position/{symbol}")
def _(symbol: str):
    return get_symbol_position(symbol)
