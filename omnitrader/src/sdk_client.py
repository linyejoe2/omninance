"""
sdk_client.py — E.SUN SDK singleton.

Reads credentials from environment variables and pre-populates the
keyring so the SDK can authenticate non-interactively inside Docker.
"""
import configparser
import logging
import os

import keyring

from esun_trade.sdk import SDK
from esun_trade.util import TRADE_SDK_ACCOUNT_KEY, TRADE_SDK_CERT_KEY, setup_keyring
from esun_marketdata import EsunMarketdata

logger = logging.getLogger(__name__)

_sdk: SDK | None = None
_marketdata_sdk: EsunMarketdata | None = None


def get_sdk() -> SDK:
    if _sdk is None:
        raise RuntimeError("SDK not initialised — call init_sdk() first")
    return _sdk

def get_marketdata_sdk() -> SDK:
    if _marketdata_sdk is None:
        raise RuntimeError("SDK not initialised — call init_sdk() first")
    return _marketdata_sdk


def init_sdk() -> None:
    global _sdk
    global _marketdata_sdk
    config = _build_config()
    account = config["User"]["Account"]
    _store_credentials(account)
    _sdk = SDK(config)
    _sdk.login()
    logger.info("[SDK] Logged in  account=%s", account)
    
    _marketdata_sdk = EsunMarketdata(config)
    _marketdata_sdk.login()
    logger.info("[Market Data SDK] Logged in  2330 last price=%s", _marketdata_sdk.rest_client.stock.intraday.quote(symbol="2330").get("lastPrice"))
    

def shutdown_sdk() -> None:
    global _sdk
    if _sdk is not None:
        _sdk.logout()
        _sdk = None
        logger.info("[SDK] Logged out")
        
def get_last_price(symbol: str) -> float:
    """
    獲取最新成交價。
    若尚未成交，則回傳參考價。
    """
    if not _marketdata_sdk:
        logger.error("[SDK] MarketData SDK not initialized")
        return 0.0

    try:
        # 呼叫 Rest API 獲取快照
        quote = _marketdata_sdk.rest_client.stock.intraday.quote(symbol=symbol, type="oddlot")
        
        if not quote:
            logger.warning(f"[SDK] No quote data found for {symbol}")
            return 0.0

        # 優先取最後成交價，若無則取參考價 (昨收)
        # 這樣在 09:00:01 這種尚未產生成交價的時間點才不會壞掉
        price = quote.get("lastPrice") or quote.get("referencePrice")
        
        return float(price) if price else 0.0

    except Exception as exc:
        logger.error(f"[SDK] Failed to get price for {symbol}: {exc}")
        return 0.0
    
def get_quote(symbol: str, type_: str):
    return _marketdata_sdk.rest_client.stock.intraday.quote(symbol=symbol, type=type_)

def get_symbol_position(symbol: str) -> int:
    inventories = get_sdk().get_inventories()

    if len(inventories) == 0:
        return 0
    
    quentity = 0

    for inventory in inventories:
        if inventory["stk_no"] == symbol:
            quentity += int(inventory["cost_qty"]) 
            quentity -= int(inventory["qty_sm"])

    return quentity
# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _build_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config["Core"] = {
        "Entry": os.environ["ESUN_ENTRY"],
        "Environment": os.environ.get("ESUN_ENVIRONMENT", "production"),
    }
    config["Cert"] = {"Path": os.environ["ESUN_CERT_PATH"]}
    config["Api"] = {
        "Key": os.environ["ESUN_API_KEY"],
        "Secret": os.environ["ESUN_API_SECRET"],
    }
    config["User"] = {"Account": os.environ["ESUN_ACCOUNT"]}
    return config


def _store_credentials(account: str) -> None:
    """Pre-populate the CryptFileKeyring from env vars (non-interactive Docker login)."""
    account_password = os.environ.get("ESUN_ACCOUNT_PASSWORD", "")
    cert_password = os.environ.get("ESUN_CERT_PASSWORD", "")
    
    setup_keyring(account)

    if account_password:
        keyring.set_password(TRADE_SDK_ACCOUNT_KEY, account, account_password)
    if cert_password:
        keyring.set_password(TRADE_SDK_CERT_KEY, account, cert_password)
