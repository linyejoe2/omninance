"""
schedule.py — Scheduled-job execution history.

  GET /api/schedules            — all known jobs + schedule + last run
  GET /api/schedules/{job}/logs — execution logs for one job, newest first
"""
from fastapi import APIRouter, HTTPException, Query

from src.service.schedule_log import JOB_SCHEDULES, list_logs, list_schedules

router = APIRouter(tags=["schedules"])


@router.get("/api/schedules")
async def get_schedules():
    return await list_schedules()


@router.get("/api/schedules/{job}/logs")
async def get_schedule_logs(job: str, limit: int = Query(default=50, ge=1, le=500)):
    if job not in JOB_SCHEDULES:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job}")
    return await list_logs(job, limit)
