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

logger = logging.getLogger(__name__)

_sdk: SDK | None = None


def get_sdk() -> SDK:
    if _sdk is None:
        raise RuntimeError("SDK not initialised — call init_sdk() first")
    return _sdk


def init_sdk() -> None:
    global _sdk
    config = _build_config()
    account = config["User"]["Account"]
    _store_credentials(account)
    _sdk = SDK(config)
    _sdk.login()
    logger.info("[SDK] Logged in  account=%s", account)


def shutdown_sdk() -> None:
    global _sdk
    if _sdk is not None:
        _sdk.logout()
        _sdk = None
        logger.info("[SDK] Logged out")


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
