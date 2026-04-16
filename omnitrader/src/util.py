def get_tick_size(price: float) -> float:
    """根據台股規則計算價格對應的 Tick Size"""
    if price < 10: return 0.01
    if price < 50: return 0.05
    if price < 100: return 0.1
    if price < 500: return 0.5
    if price < 1000: return 1.0
    return 5.0