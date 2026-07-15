from datetime import datetime
from typing import Annotated, Any, Dict, Optional
from pydantic import BaseModel, Field, BeforeValidator

# 將 MongoDB 的 ObjectId 轉換為字串的輔助型別
PyObjectId = Annotated[str, BeforeValidator(str)]

class TickerModel(BaseModel):
    """日 K 線資料 (OHLCV) 模型"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    symbol: str = Field(..., description="股票代號，例如: 2330.TW")
    date: str = Field(..., description="資料日期，格式: YYYY-MM-DD")
    open: float = Field(..., alias="Open")
    high: float = Field(..., alias="High")
    low: float = Field(..., alias="Low")
    close: float = Field(..., alias="Close")
    volume: int = Field(..., alias="Volume")

    class Config:
        populate_by_name = True  # 允許使用別名 (Open/High...) 或欄位名初始化
        json_schema_extra = {
            "example": {
                "symbol": "2330.TW",
                "date": "2026-07-14",
                "Open": 1000.0,
                "High": 1010.0,
                "Low": 995.0,
                "Close": 1005.0,
                "Volume": 25000000
            }
        }