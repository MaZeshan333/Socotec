import os
import psycopg2
from dotenv import load_dotenv

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
    # Import task list (filename, target table name)
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
        # 1. Preprocessing: Set date format
        cur.execute("SET DateStyle = 'ISO, DMY';")

        # 2. Cleanup: Reset all tables
        print("Cleaning database tables...")
        all_tables = [t[1] for t in import_tasks]
        cur.execute(f"TRUNCATE TABLE {', '.join(all_tables)} RESTART IDENTITY CASCADE;")
        
        # 3. Import: Use dynamic column name mapping
        for file_name, table_name in import_tasks:
            file_path = os.path.join(NEW_DIR, file_name)
            if not os.path.exists(file_path):
                print(f"Skipping non-existent file: {file_name}")
                continue

            print(f"Importing {table_name}...")
            with open(file_path, 'r', encoding='utf-8') as f:
                header = f.readline().strip() # Get column names from CSV
                f.seek(0)
                # Key point: Specify (col1, col2...) mapping, database automatically handles missing auto-increment ID columns
                sql = f"COPY {table_name} ({header}) FROM STDIN WITH CSV HEADER"
                cur.copy_expert(sql, f)
        
        conn.commit()
        print("\nData import successful!")

    except Exception as e:
        print(f"\nImport failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    clear_and_import()
