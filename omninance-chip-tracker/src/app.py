"""
app.py — FastAPI service entry point.

Scheduler: Mon–Fri 09:30 Asia/Taipei  →  run_pipeline() with one retry.
Manual trigger: POST /api/trigger
Health check:   GET  /health
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from src.pipeline import run_pipeline
from src.routes.backtest import router as backtest_router
from src.routes.signals import router as signals_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_RETRY_DELAY_SECONDS = 60
scheduler = AsyncIOScheduler()


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
                    _RETRY_DELAY_SECONDS,
                    exc,
                )
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
            else:
                logger.error("[Pipeline] Attempt 2 failed — giving up. Error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        execute_pipeline,
        CronTrigger(day_of_week="mon-fri", hour=14, minute=2, timezone="Asia/Taipei"),
        id="daily_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[Scheduler] Started — daily pipeline at 09:30 Asia/Taipei (Mon–Fri)")
    yield
    scheduler.shutdown()
    logger.info("[Scheduler] Stopped")


app = FastAPI(title="Omninance Chip Tracker", lifespan=lifespan)
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
