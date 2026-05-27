import os
import psycopg2
from dotenv import load_dotenv
import io  # Used for handling in-memory text streams

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME_NEW")
    )

def clear_and_import():
    NEW_DIR = 'New'
    LIMIT = 30  # Set import row limit
    
    import_tasks = [
        ('projects.csv', 'projects'),
        ('sites.csv', 'sites'),
        ('gateways.csv', 'gateways'),
        ('site_gateways.csv', 'site_gateways'),
        ('configs.csv', 'configs'),
        ('raw_measurements.csv', 'raw_measurements')
    ]

    conn = get_connection()
    cur = conn.cursor()

    try:
        # 1. Preprocessing
        cur.execute("SET DateStyle = 'ISO, DMY';")

        # 2. Cleanup
        print("Cleaning database tables...")
        all_tables = [t[1] for t in import_tasks]
        cur.execute(f"TRUNCATE TABLE {', '.join(all_tables)} RESTART IDENTITY CASCADE;")
        
        # 3. Import (only first LIMIT rows)
        for file_name, table_name in import_tasks:
            file_path = os.path.join(NEW_DIR, file_name)
            if not os.path.exists(file_path):
                print(f"Skipping non-existent file: {file_name}")
                continue

            print(f"Importing {table_name} (limited to first {LIMIT} rows)...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                # Get header
                header_line = f.readline().strip()
                
                # Read the next LIMIT lines of data
                lines = [header_line + '\n']
                for _ in range(LIMIT):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)
                
                # Convert collected lines into an in-memory file object (StringIO)
                limited_data = io.StringIO(''.join(lines))
                
                # Execute import
                sql = f"COPY {table_name} ({header_line}) FROM STDIN WITH CSV HEADER"
                cur.copy_expert(sql, limited_data)
        
        conn.commit()
        print("\nPartial data import successful!")

    except Exception as e:
        print(f"\nImport failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    clear_and_import()
