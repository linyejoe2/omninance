import sqlite3
import pandas as pd

class Database:
    def __init__(self, db_name="database/omninance.db"):
        self.db_name = db_name
        self._init_history_table()

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
        """排序規則：釘選優先 -> 最後更新時間倒序"""
        with sqlite3.connect(self.db_name) as conn:
            return pd.read_sql("""
                SELECT * FROM search_history 
                ORDER BY is_pinned DESC, updated_at DESC
            """, conn).to_dict('records')

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
        
db = Database()