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
    # 导入任务列表 (文件名, 目标表名)
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
        # 1. 预处理：设置日期格式
        cur.execute("SET DateStyle = 'ISO, DMY';")

        # 2. 清理：重置所有表
        print("清理数据库表中...")
        all_tables = [t[1] for t in import_tasks]
        cur.execute(f"TRUNCATE TABLE {', '.join(all_tables)} RESTART IDENTITY CASCADE;")
        
        # 3. 导入：使用动态列名映射
        for file_name, table_name in import_tasks:
            file_path = os.path.join(NEW_DIR, file_name)
            if not os.path.exists(file_path):
                print(f"跳过不存在的文件: {file_name}")
                continue

            print(f"正在导入 {table_name}...")
            with open(file_path, 'r', encoding='utf-8') as f:
                header = f.readline().strip() # 获取 CSV 中的列名
                f.seek(0)
                # 关键：指定 (col1, col2...) 映射，数据库会自动处理缺失的自增 ID 列
                sql = f"COPY {table_name} ({header}) FROM STDIN WITH CSV HEADER"
                cur.copy_expert(sql, f)
        
        conn.commit()
        print("\n数据导入成功！")

    except Exception as e:
        print(f"\n导入失败: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    clear_and_import()