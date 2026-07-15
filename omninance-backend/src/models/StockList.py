from typing import Annotated, Optional
from pydantic import BaseModel, Field, BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class StockListModel(BaseModel):
    """追蹤股票清單（依市值排名）模型"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    symbol: str = Field(..., description="股票代號，例如: 2330.TW")
    name: Optional[str] = Field(default=None, description="公司名稱")
    date: Optional[str] = Field(default=None, description="市值資料日期，格式: YYYY-MM-DD")
    rank: Optional[int] = Field(default=None, description="市值排名")
    capitals: Optional[float] = Field(default=None, description="發行股數")
    close: Optional[float] = Field(default=None, description="收盤價")
    mkt_val: Optional[float] = Field(default=None, description="當日市值 (百萬)")
    mkt_val_ratio: Optional[float] = Field(default=None, description="市值佔大盤比重")
    desc: Optional[str] = Field(default=None, description="備註說明")
    tag: Optional[str] = Field(default=None, description="產業標籤")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "symbol": "2330.TW",
                "name": "台積電",
                "date": "2026-04-08",
                "rank": 1,
                "mkt_val": 50249091.66,
                "mkt_val_ratio": 0.44298,
                "tag": "AI",
            }
        }
