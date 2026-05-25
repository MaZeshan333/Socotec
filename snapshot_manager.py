# snapshot_manager.py
import psycopg2
import json

def get_compressed_snapshot(db_params, chat, question, threshold=10):
    """
    Adaptive Schema Retrieval:
    - Small Database (Table count <= threshold): Full fetch to preserve foreign key links.
    - Large Database (Table count > threshold): LLM filters relevant tables to prevent Token explosion.
    """
    print("[Data Fetching] Scanning database schema...")
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()
    
    # 1. Fetch all table names first
    cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';")
    all_tables = [r[0] for r in cur.fetchall()]
    table_count = len(all_tables)
    
    relevant_tables = []
    
    # 2. Decide strategy based on database size
    if table_count <= threshold:
        # Case A: Small database, skip LLM filtering
        print(f"[Strategy Selection] Small database detected ({table_count} tables). Performing full schema fetch to ensure JOIN integrity.")
        relevant_tables = all_tables
    else:
        # Case B: Large database, perform LLM compression
        print(f"[Strategy Selection] Large database detected ({table_count} tables). Calling LLM to filter relevant tables...")
        prompt = f"""You are a database architect. Here are all the table names in the database: {', '.join(all_tables)}.
The user's task is: "{question}"
Please select the core tables likely related to the task, along with any intermediate bridging tables needed to connect them.
Return ONLY comma-separated table names (e.g., table1,table2) without any explanation."""
        
        relevant_tables_str = chat.ask(prompt, role="judge")
        # Filter out potential hallucinations, ensuring tables exist in the database
        relevant_tables = [t.strip() for t in relevant_tables_str.split(',') if t.strip() in all_tables]
        
        if not relevant_tables: # Fallback for extreme cases
            relevant_tables = all_tables[:threshold]
        print(f"[Info Compression] Filtering complete. Retained {len(relevant_tables)} critical tables.")

    # 3. Extract column details and samples for designated tables
    snapshot = "[Compact Database Schema Description]\n"
    for table in relevant_tables:
        # Extract column names and data types
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}';")
        cols = cur.fetchall()
        snapshot += f"- Table {table}: {', '.join([f'{c[0]}({c[1]})' for c in cols])}\n"
        
        # Extract 1 sample row and truncate long values
        try:
            cur.execute(f"SELECT * FROM {table} LIMIT 1;")
            col_names = [d[0] for d in cur.description]
            rows = cur.fetchall()
            if rows:
                sample_dict = dict(zip(col_names, rows[0]))
                # Limit value display length to prevent massive text from polluting context
                clean_sample = {k: str(v)[:100] + ("..." if len(str(v)) > 100 else "") for k, v in sample_dict.items()}
                snapshot += f"  Data Sample: {json.dumps(clean_sample, ensure_ascii=False)}\n"
        except Exception as e:
            snapshot += f"  (No sample data available or read failed)\n"
            
    cur.close()
    conn.close()
    return snapshot