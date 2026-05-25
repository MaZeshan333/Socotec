# sql_engine.py
import psycopg2
import pandas as pd
import time

class PGSqlEngine:
    def __init__(self, db_params):
        self.params = db_params

    def execute_and_print(self, sql):
        start_time = time.time()
        print(f"[Database Execution] Running SQL query...")
        try:
            conn = psycopg2.connect(**self.params)
            # Use pandas to load data
            df = pd.read_sql_query(sql, conn)
            conn.close()
            
            duration = time.time() - start_time
            print(f"[Execution Success] Time taken: {duration:.2f}s | Rows returned: {len(df)}")
            return {"status": "success", "df": df, "csv": df.to_csv(index=False)}
        except Exception as e:
            print(f"[Execution Failure] Error message: {str(e)}")
            return {"status": "error", "message": str(e)}