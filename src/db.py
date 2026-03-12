import sqlite3
import pandas as pd
import requests

class Database:
    def __init__(self, db_name="database/omninance.db"):
        self.db_name = db_name
        self._init_history_table()
        self._init_stock_list_table()

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
        
db = Database()
with sqlite3.connect(db.db_name) as conn:
    count = conn.execute("SELECT COUNT(*) FROM stock_list").fetchone()[0]
    # if count == 0:
    added_count = db.update_stock_list_from_twse()