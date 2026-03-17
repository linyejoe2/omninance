import sqlite3
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_name="database/omninance.db"):
        self.db_name = db_name
        self._init_history_table()
        self._init_stock_list_table()
        self.init_ndc_table()
        # self.sync_stock_holder_data("2377.TW")

    def save_data(self, table_name, df, if_exists="replace"):
        """將 DataFrame 存入 SQLite"""
        with sqlite3.connect(self.db_name) as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=True)

    def load_data(self, table_name):
        """從 SQLite 讀取資料"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                return pd.read_sql(f"SELECT * FROM {table_name}", conn, index_col="Date", parse_dates="Date")
        except Exception:
            return None
        
    def _init_history_table(self):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    symbol TEXT PRIMARY KEY,
                    is_pinned INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    def init_stock_list(self):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_list (
                    symbol TEXT PRIMARY KEY,
                    name TEXT
                )
            """)
            
    def search_stocks(query):
        """回傳符合條件的股票清單 [(symbol, name), ...]"""
        if not query: return []
        query = f"%{query}%"
        with sqlite3.connect("omninance.db") as conn:
            cursor = conn.execute("""
                SELECT symbol, name FROM stock_list 
                WHERE symbol LIKE ? OR name LIKE ?
                LIMIT 10
            """, (query, query))
            return cursor.fetchall()

    def get_search_history(self):
        """
        排序規則：釘選優先 -> 最後更新時間倒序
        同時關聯 stock_list 取得名稱
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                # 使用 LEFT JOIN，如果 stock_list 還沒建好或找不到名稱，也能顯示代碼
                query = """
                    SELECT h.symbol, h.is_pinned, h.updated_at, s.name 
                    FROM search_history h
                    LEFT JOIN stock_list s ON h.symbol = s.symbol
                    ORDER BY h.is_pinned DESC, h.updated_at DESC
                """
                return pd.read_sql(query, conn).to_dict('records')
        except Exception as e:
            print(f"Error fetching history: {e}")
            return []

    def add_or_update_history(self, symbol):
        """新增或更新訪問時間"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                INSERT INTO search_history (symbol, updated_at) VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(symbol) DO UPDATE SET updated_at=CURRENT_TIMESTAMP
            """, (symbol.upper(),))

    def toggle_pin(self, symbol, current_status):
        new_status = 1 if current_status == 0 else 0
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("UPDATE search_history SET is_pinned = ? WHERE symbol = ?", (new_status, symbol))

    def delete_history(self, symbol):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("DELETE FROM search_history WHERE symbol = ?", (symbol,))
            
    def _init_stock_list_table(self):
        """建立儲存台股代碼與名稱的字典表"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_list (
                    symbol TEXT PRIMARY KEY,
                    name TEXT,
                    market_type TEXT
                )
            """)
            
    def update_stock_list_from_twse(self):
        """抓取證交所清單並存入資料庫"""
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        
        # 1. 抓取網頁表格
        response = requests.get(url)
        response.encoding = 'big5' # 證交所使用 big5 編碼
        
        # 2. 解析 HTML (通常第一張表就是資料)
        dfs = pd.read_html(response.text)
        df = dfs[0]
        
        # 3. 清洗資料
        # 設定欄位名稱（證交所表格通常第一列是標題）
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        
        # 證交所資料格式為 "2330 台積電"，我們需要拆分
        # 我們只取「有價證券代號及名稱」這一欄
        # 並且過濾出股票 (通常是四位數字) 或 ETF
        
        stock_data = []
        for _, row in df.iterrows():
            raw_text = str(row['有價證券代號及名稱'])
            if '　' in raw_text:
                symbol, name = raw_text.split('　', 1)
                # 簡單過濾：代碼長度為 4 (股票) 或 5-6 (ETF)
                if len(symbol) >= 4:
                    # 統一加上 .TW 符合 yfinance 格式
                    formatted_symbol = f"{symbol}.TW"
                    stock_data.append((formatted_symbol, name, row['市場別']))
        
        # 4. 寫入資料庫
        with sqlite3.connect(self.db_name) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO stock_list (symbol, name, market_type)
                VALUES (?, ?, ?)
            """, stock_data)
        
        return len(stock_data)
    
    def init_ndc_table(self):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS business_indicators (
                    report_month TEXT PRIMARY KEY, -- 格式: 2026-01
                    score INTEGER
                )
            """)

    def sync_business_cycle_data(self):
        """利用 Excel 連結同步景氣燈號"""
        # 這是你提供的國發會 Excel 載點
        url = 'https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNTc4MS82MzkyL2FmYWU2OGQ1LWVjNzktNDg5NC04ODFjLTI0M2E1Nzg2ODBlZC54bHN4&n=5paw6IGe56i%2f6ZmE5Lu25pW45YiXLnhsc3g%3d&icon=.xlsx'
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # 使用 BytesIO 讀取 Excel
            df_raw = pd.read_excel(BytesIO(response.content))
            
            # 1. 清洗資料：根據 Excel 內容鎖定欄位
            # 假設 Excel 欄位為 'DATE' 和 '景氣對策信號綜合分數'
            if 'DATE' in df_raw.columns:
                df_raw = df_raw.set_index('DATE')
            
            # 2. 篩選出分數列並重命名
            # 我們只要分數這一欄，並過濾掉空值
            target_column = '景氣對策信號綜合分數'
            if target_column in df_raw.columns:
                score_series = df_raw[target_column].dropna()
                
                # 轉成我們資料庫要的格式 (YYYY-MM, score)
                # 將索引轉為字串格式 2024-01
                sync_df = score_series.reset_index()
                sync_df.columns = ['report_month', 'score']
                sync_df['report_month'] = pd.to_datetime(sync_df['report_month']).dt.strftime('%Y-%m')
                
                # 3. 寫入資料庫
                with sqlite3.connect(self.db_name) as conn:
                    sync_df.to_sql('business_indicators', conn, if_exists='replace', index=False)
                
                return True, f"已成功從 Excel 更新 {len(sync_df)} 筆燈號數據"
            else:
                return False, "Excel 中找不到 '景氣對策信號綜合分數' 欄位"
                
        except Exception as e:
            return False, f"Excel 同步失敗: {str(e)}"

    def _get_all_business_indicators(self):
        """從本地資料庫獲取所有燈號數據"""
        try:
            with sqlite3.connect(self.db_name) as connection:
                query = "SELECT report_month, score FROM business_indicators ORDER BY report_month ASC"
                data_frame = pd.read_sql(query, connection)
                
                # 將 report_month 轉為 datetime index 方便後續對齊
                data_frame['report_month'] = pd.to_datetime(data_frame['report_month'])
                data_frame.set_index('report_month', inplace=True)
                return data_frame['score']
        except Exception:
            return pd.Series(dtype='float64')
        
    def sync_stock_holder_data(self, symbol):
        """
        抓取股權分配表
        symbol 格式: 2330.TW -> 需轉為 2330
        """
        stock_code = symbol.split('.')[0]
        url = f"https://norway.twsthr.info/StockHolders.aspx?stock={stock_code}"
        
        try:
            # 該網站有基本的防爬蟲，需加上 Header
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            response.encoding = 'utf-8'
            
            # 解析表格
            dfs = pd.read_html(response.text)
            df = None
            df = dfs[13]
            df = df.iloc[:-2, 2:18].dropna(how='all')
            df.columns = df.iloc[0]
            df = df.rename(columns={"資料日期": "Date"})
            df = df.iloc[1:].reset_index(drop=True)
            
            if df is None: return False, "找不到股權表格"
            
            # 存入資料庫
            with sqlite3.connect(self.db_name) as conn:
                df.to_sql(f"stock_holders_{stock_code}", conn, if_exists='replace', index=False, method=None)
            return True, "籌碼資料同步成功"
        except Exception as e:
            return False, f"爬取失敗: {e}"
        
    def get_stock_holder_history(self, symbol):
        stock_code = symbol.split('.')[0]
        table_name = f"stock_holders_{stock_code}"
        need_sync = False
        
        # 1. 檢查資料表是否存在
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                need_sync = True
            else:
                # 2. 檢查最新一筆資料的日期
                try:
                    cursor.execute(f"SELECT MAX(Date) FROM {table_name}")
                    last_date_str = cursor.fetchone()[0]
                    if last_date_str:
                        last_date = datetime.strptime(last_date_str, '%Y%m%d')
                        # 如果最新資料距離今天超過 5 天，則需要更新
                        if (datetime.now() - last_date) > timedelta(days=5):
                            need_sync = True
                    else:
                        need_sync = True
                except Exception as e:
                    print(f"檢查日期時發生錯誤: {e}")
                    need_sync = True
            
        # 2. 如果不存在，調用同步功能進行初始化
        if need_sync:
            print(f"初始化大戶持股資料: {symbol}")
            success, message = self.sync_stock_holder_data(symbol)
            if not success:
                print(f"初始化同步失敗: {message}")
                return []

        # 3. 讀取數據
        try:
            with sqlite3.connect(self.db_name) as conn:
                query = f"SELECT * FROM {table_name} ORDER BY Date ASC"
                return pd.read_sql(query, conn)
        except Exception as e:
            print(f"Error fetching history: {e}")
            return []
        
db = Database()
with sqlite3.connect(db.db_name) as conn:
    count = conn.execute("SELECT COUNT(*) FROM stock_list").fetchone()[0]
    # if count == 0:
    added_count = db.update_stock_list_from_twse()