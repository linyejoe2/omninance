import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def connect() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(os.environ["MONGO_URI"])
    _db = _client[os.environ["MONGO_DB_NAME"]]
    


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
