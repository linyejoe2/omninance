import requests
import pandas as pd
import random

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_TSC_market_capital() -> int:
    """
    取得上市市場（TSC）目前的總市值。

    Returns:
        int: 上市市場總市值，單位為：新台幣百萬元。
    """
    random_num = int(random.random() * 1000000)
    url=f"https://www.twse.com.tw/rwd/homeApi/mkt_cap?_={random_num}"
    df=pd.read_json(url)

    mkt_val = df[1][len(df) - 1]
    
    return int(mkt_val * 100)

def get_OTC_market_capital() -> int:
    """
    取得上櫃市場（OTC）目前的總市值。

    Returns:
        int: 上櫃市場總市值，單位為：新台幣百萬元。
    """
    response = requests.post("https://www.tpex.org.tw/www/zh-tw/afterTrading/highlight", headers=headers)

    response = response.json()

    mkt_val = int((response["tables"][0]["data"][0][2]).replace(",", ""))
    
    return mkt_val

def get_TSC_top_series_by_market_cap(pick_count: int) -> pd.DataFrame:
    """
    取得上市市場（TSC）市值排名前 N 名的個股清單與比例。

    Args:
        pick_count (int): 欲選取的個股數量（排名深度）。

    Returns:
        pd.DataFrame: 包含市值排名的資料表，欄位如下：
            - rank: 市值排名
            - symbol: 證券代號
            - name: 公司名稱
            - mkt_val_ratio: 市值佔比 (%)
            - mkt_val: 當日市值 (百萬)
    """
    url='https://www.taifex.com.tw/cht/9/futuresQADetail'
    df=pd.read_html(url, encoding='big5-hkscs')[0]

    df = df.iloc[:pick_count, :-4]

    df = df.rename(columns={"排行":	"rank", "證券名稱": "symbol", "證券名稱.1": "name", "市值佔 大盤比重": "mkt_val_ratio"})

    df["mkt_val_ratio"] = ((df["mkt_val_ratio"].str.replace("%", "")).astype("float") / 100).round(5)

    mkt_cap = get_TSC_market_capital()

    df["mkt_val"] = (df["mkt_val_ratio"] * mkt_cap).round(2)
    
    return df

def get_OTC_top_series_by_market_cap(pick_count: int) -> pd.DataFrame:
    """
    取得上櫃市場（OTC）市值排名前 N 名的個股清單與比例。

    Args:
        pick_count (int): 欲選取的個股數量（排名深度）。

    Returns:
        pd.DataFrame: 包含市值排名的資料表，欄位如下：
            - date: 資料日期
            - rank: 市值排名
            - symbol: 證券代號
            - name: 公司名稱
            - capitals: 發行股數 (股)
            - close: 收盤價
            - mkt_val: 當日市值 (百萬)
            - mkt_val_ratio: 市值佔比 (%)
    """
    url='https://www.tpex.org.tw/openapi/v1/tpex_mainborad_highlight'
    marketCapitalization=pd.read_json(url)["MarketCapitalization"][0]

    url='https://www.tpex.org.tw/openapi/v1/tpex_daily_market_value'
    df=pd.read_json(url)

    df = df.iloc[:pick_count]

    df["MarketValueRatio"] = (df["MarketValue"] / marketCapitalization).round(5)
    
    df = df.rename(columns={"Date": "date", "Capitals": "capitals", "ClosePrice": "close","SecuritiesCompanyCode": "symbol", "Rank": "rank", "CompanyName": "name", "MarketValue": "mkt_val", "MarketValueRatio": "mkt_val_ratio"})

    return df

# get_OTC_top_series_by_market_cap(50)
# # get_OTC_market_capital()

class Tee(object):
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush() # 確保即時寫入
    def flush(self):
        for f in self.files:
            f.flush()