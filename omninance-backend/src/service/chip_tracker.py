import httpx
import logging
import os
import time

logger = logging.getLogger(__name__)

_CHIP_TRACKER_URL = os.environ.get("CHIP_TRACKER_URL", "http://chip-tracker:8000")

def fetch_signals_with_retry(settings: dict, max_retries: int = 3) -> tuple:
    """封裝 API 呼叫與重試邏輯"""
    retry_delay = 300  # 5 分鐘
    
    for i in range(max_retries):
        try:
            with httpx.Client(base_url=_CHIP_TRACKER_URL, timeout=120.0) as ct:
                resp = ct.post("/api/signals/compute", json=settings)
                resp.raise_for_status()
                data = resp.json()
                
                # 解析 API 回傳格式
                buy_list = data.get("actions", {}).get("buy", [])
                sell_hint = data.get("actions", {}).get("sell_hint", [])
                snapshot = data.get("snapshot", {})
                
                return buy_list, sell_hint, snapshot, None
                
        except Exception as exc:
            logger.warning(f"[API Retry] Attempt {i+1} failed: {exc}")
            if i < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return [], [], {}, str(exc)