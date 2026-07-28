"""
schedule_log.py — Execution logging for scheduled jobs.

Every scheduled run (all of them ofelia-triggered — see /ofelia.ini) is
recorded in the schedule_log collection so the dashboard 排程 page can show
per-job execution history.
"""
import logging
from typing import Any, Awaitable, Callable

from src.core.date_time_util import get_datetime
from src.models import db as mongo_db
from src.models.ScheduleLog import ScheduleLogModel

logger = logging.getLogger(__name__)

# job name -> human-readable schedule (shown on the dashboard)
JOB_SCHEDULES: dict[str, str] = {
    "stock-list-refresh": "@hourly (ofelia)",
    "ticker-refresh": "@hourly (ofelia)",
    "holder-refresh": "0 5 * * * * (ofelia)",
    "daily_strategies": "Mon–Fri 10:04 (ofelia)",
    "finalize_daily_settlement": "Mon–Fri 15:00 (ofelia)",
    "nightly_signal_generate": "Mon–Fri 15:30 (ofelia)",
}


async def run_with_log(job: str, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    """Run *func*, record the outcome in schedule_log, then return (or re-raise)."""
    started = get_datetime()
    try:
        result = await func(*args, **kwargs)
    except Exception as exc:
        await _insert(job, "failed", started, {"error": str(exc)})
        raise
    await _insert(job, "success", started, result)
    return result


async def _insert(job: str, status: str, started, output: Any) -> None:
    finished = get_datetime()
    doc = {
        "job": job,
        "status": status,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": int((finished - started).total_seconds() * 1000),
        "output": output,
    }
    try:
        await mongo_db.get_db()["schedule_log"].insert_one(doc)
    except Exception as exc:
        # Logging must never break the job itself
        logger.error(f"[ScheduleLog] Failed to record log for {job}: {exc}")


async def list_schedules() -> list[dict]:
    """All known jobs with their schedule and most recent run."""
    db = mongo_db.get_db()
    schedules = []
    for job, schedule in JOB_SCHEDULES.items():
        doc = await db["schedule_log"].find_one({"job": job}, sort=[("started_at", -1)])
        last_run = (
            ScheduleLogModel(**doc).model_dump(exclude={"id", "output"}) if doc else None
        )
        schedules.append({"job": job, "schedule": schedule, "last_run": last_run})
    return schedules


async def list_logs(job: str, limit: int = 50) -> list[dict]:
    """Execution logs for one job, newest first."""
    cursor = (
        mongo_db.get_db()["schedule_log"]
        .find({"job": job})
        .sort("started_at", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=None)
    return [ScheduleLogModel(**doc).model_dump(exclude={"id"}) for doc in docs]
