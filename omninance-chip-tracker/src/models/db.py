import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(os.environ["MONGO_URI"])
    _db = _client[os.environ["MONGO_DB_NAME"]]
    
    # ==== 自動建立索引 (確保 symbol + date 唯一) ====
    # 1. Tickers 索引
    await _db["tickers"].create_index(
        [("symbol", ASCENDING), ("date", ASCENDING)], 
        unique=True
    )
    
    # 2. Holders 索引
    await _db["holders"].create_index(
        [("symbol", ASCENDING), ("date", ASCENDING)], 
        unique=True
    )
    print("MongoDB Connected & Indexes Created.")
    


def disconnect() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not connected")
    return _db
