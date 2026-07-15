from typing import Annotated, Any, Dict, Optional
from pydantic import BaseModel, Field, BeforeValidator, model_validator

PyObjectId = Annotated[str, BeforeValidator(str)]

class HolderSummaryModel(BaseModel):
    """大股東持股統計摘要模型"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    
    # 基礎欄位
    symbol: str = Field(..., description="股票代號，例如: 0050.TW")
    date: str = Field(..., description="資料日期 (YYYYMMDD)")
    
    # 統計數據 (對應 data 內部的中文欄位)
    total_sheets: int = Field(..., description="集保總張數")
    total_shareholders: int = Field(..., description="總股東人數")
    avg_sheets_per_person: float = Field(..., description="平均張數/人")
    
    # >400張 大股東資訊
    over400_sheets: int = Field(..., description=">400張大股東 持有張數")
    over400_percentage: float = Field(..., description=">400張大股東 持有百分比")
    over400_count: int = Field(..., description=">400張大股東 人數")
    
    # 分級人數區間
    count_400_to_600: int = Field(..., description="400~600張人數")
    count_600_to_800: int = Field(..., description="600~800張人數")
    count_800_to_1000: int = Field(..., description="800~1000張人數")
    
    # >1000張 大股東資訊
    over1000_count: int = Field(..., description=">1000張人數")
    over1000_percentage: float = Field(..., description=">1000張大股東 持有百分比")
    
    # 市場資訊
    close_price: float = Field(..., description="收盤價")