"""
app.py — Omninance Chip Tracker FastAPI service entry point.

Pipeline scheduling has moved to omninance-backend.
Manual trigger: POST /api/trigger
Health check:   GET  /health
"""
import asyncio

from fastapi import FastAPI

from src.pipeline import run_pipeline
from src.routes.backtest import router as backtest_router
from src.routes.signals import router as signals_router
from src.core.logging_util import start_logging

logger = start_logging()

_RETRY_DELAY_SECONDS = 60


async def execute_pipeline() -> None:
    """Run the data pipeline with one automatic retry on failure."""
    for attempt in range(2):
        try:
            logger.info("[Pipeline] Starting (attempt %d/2)", attempt + 1)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, run_pipeline)
            logger.info("[Pipeline] Completed successfully")
            return
        except Exception as exc:
            if attempt == 0:
                logger.warning(
                    "[Pipeline] Attempt 1 failed — retrying in %ds. Error: %s",
                    _RETRY_DELAY_SECONDS, exc,
                )
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
            else:
                logger.error("[Pipeline] Attempt 2 failed — giving up. Error: %s", exc)


app = FastAPI(title="Omninance Chip Tracker")
app.include_router(backtest_router)
app.include_router(signals_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/trigger")
async def manual_trigger():
    """Manually trigger the data pipeline (non-blocking)."""
    asyncio.create_task(execute_pipeline())
    logger.info("[Trigger] Manual pipeline trigger received")
    return {"status": "triggered"}
