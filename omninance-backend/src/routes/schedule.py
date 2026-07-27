"""
schedule.py — Scheduled-job execution history.

  GET  /api/schedules              — all known jobs + schedule + last run
  GET  /api/schedules/{job}/logs   — execution logs for one job, newest first
  POST /api/schedules/{job}/trigger — force-run a job now, outside its normal schedule
"""
from fastapi import APIRouter, HTTPException, Query

from src.scheduler import trigger_job as trigger_aps_job
from src.service.holder_data import refresh_holders
from src.service.schedule_log import JOB_SCHEDULES, list_logs, list_schedules, run_with_log
from src.service.stock_list import refresh_stock_list
from src.service.ticker_data import refresh_tickers

router = APIRouter(tags=["schedules"])

# ofelia-triggered jobs run as plain async functions on this service — force
# execution just awaits them directly. The APScheduler jobs (daily_strategies,
# etc.) are triggered via the scheduler's own /trigger/{job_id} route instead,
# since they are registered jobs rather than free-standing functions.
REFRESH_JOBS = {
    "stock-list-refresh": refresh_stock_list,
    "ticker-refresh": refresh_tickers,
    "holder-refresh": refresh_holders,
}


@router.get("/api/schedules")
async def get_schedules():
    return await list_schedules()


@router.get("/api/schedules/{job}/logs")
async def get_schedule_logs(job: str, limit: int = Query(default=50, ge=1, le=500)):
    if job not in JOB_SCHEDULES:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job}")
    return await list_logs(job, limit)


@router.post("/api/schedules/{job}/trigger")
async def trigger_schedule(job: str):
    if job not in JOB_SCHEDULES:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job}")
    if job in REFRESH_JOBS:
        result = await run_with_log(job, REFRESH_JOBS[job])
        return {"status": "executed", "result": result}
    return await trigger_aps_job(job)
