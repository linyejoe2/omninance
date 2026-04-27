
import httpx
import asyncio
import os

_OMNITRADER_URL = os.environ.get("OMNITRADER_URL", "http://localhost:8504")

def _to_stock_no(symbol: str) -> str:
    return symbol.split(".")[0]

async def get_quote(symbol: str) -> float:
    """取得即時報價"""
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        resp = await client.get(f"/api/market/quote/{_to_stock_no(symbol)}")
        resp.raise_for_status()
        return float(resp.text)
    

if __name__ == "__main__":
    price = asyncio.run(get_quote("3481.TW"))
    print(price)