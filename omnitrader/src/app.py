"""
app.py — OmniTrader FastAPI service entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from src.sdk_client import init_sdk, shutdown_sdk, get_sdk
from src.routes.orders import router as orders_router
from src.routes.account import router as account_router
from src.routes.market import router as market_router

from src.core.logging_util import start_logging

logger = start_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sdk()
    yield
    shutdown_sdk()


app = FastAPI(
    title="OmniTrader",
    lifespan=lifespan,
    docs_url="/api-docs",
    redoc_url="/api-docs/redoc",
    openapi_url="/api-docs/openapi.json",
)

app.include_router(orders_router)
app.include_router(account_router)
app.include_router(market_router)


@app.get("/health")
def health_check():
    try:
        # 嘗試呼叫 SDK 的一個輕量級方法，確認連線與解析正常
        # 如果 get_market_status 太重，找一個更輕的 (例如 check_connection)
        get_sdk().get_inventories() 
        return {"status": "ok"}
    except Exception as e:
        # 如果 SDK 報錯 (例如你遇到的 ValueError)，回傳 500
        return Response(
            content=f"SDK Error: {str(e)}", 
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
