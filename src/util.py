import numpy as np
from CONST import colors

def bounded_cumsum(signals, lower_bound=-10.0, upper_bound=10.0):
    n = len(signals)
    result = np.zeros(n)
    current_val = 0.0
    # print(signals)
    
    for i in range(n):
        # print(i)
        # print(current_val)
        # print(signals[i])
        # 核心邏輯：先相加，立即限制邊界，再作為下一次的基礎
        current_val = current_val + float(signals[i])
        if current_val > upper_bound:
            current_val = upper_bound
        elif current_val < lower_bound:
            current_val = lower_bound
        result[i] = current_val
        # print(result[i])
        
    return result

def get_line_color(index: int) -> str: 
    length = len(colors)
    if index >= length:
        index = index % length
    return colors[index]