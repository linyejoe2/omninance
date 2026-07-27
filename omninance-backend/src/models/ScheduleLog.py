from datetime import datetime
from typing import Annotated, Any, Optional
from pydantic import BaseModel, Field, BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]


class ScheduleLogModel(BaseModel):
    """排程執行紀錄模型"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    job: str = Field(..., description="排程名稱，例如: stock-list-refresh")
    status: str = Field(..., description="執行結果: success | failed")
    started_at: datetime = Field(..., description="開始時間 (UTC)")
    finished_at: datetime = Field(..., description="結束時間 (UTC)")
    duration_ms: int = Field(..., description="執行耗時 (毫秒)")
    output: Optional[Any] = Field(default=None, description="執行輸出 (JSON)")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "job": "stock-list-refresh",
                "status": "success",
                "started_at": "2026-07-24T02:00:00Z",
                "finished_at": "2026-07-24T02:00:41Z",
                "duration_ms": 41000,
                "output": {"total": 50, "updated": 50, "skipped": 0, "failed": []},
            }
        }
