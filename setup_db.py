import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# 加载配置
load_dotenv()

def get_connection(db_name):
    """通用的数据库连接辅助函数"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=db_name
    )

def setup_database():
    new_db = os.getenv("DB_NAME_NEW")
    
    # --- 第一步：连接到 'postgres' 默认库来创建新数据库 ---
    conn = get_connection(os.getenv("DB_NAME_DEFAULT"))
    conn.autocommit = True  # 创建数据库必须在事务之外运行
    cur = conn.cursor()

    try:
        print(f"正在创建数据库: {new_db}...")
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_db)))
        print(f"数据库 '{new_db}' 创建成功！")
    except psycopg2.errors.DuplicateDatabase:
        print(f"数据库 '{new_db}' 已存在，跳过创建。")
    except Exception as e:
        print(f"创建数据库失败: {e}")
    finally:
        cur.close()
        conn.close()

    # --- 第二步：连接到新创建的数据库，初始化表结构 ---
    conn = get_connection(new_db)
    cur = conn.cursor()
    
    # 所有的建表语句（已移除 PostGIS 的 GEOMETRY 类型）
    commands = [
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            country TEXT,
            client_company_name TEXT,
            time_zone TEXT DEFAULT 'UTC',
            city TEXT,
            start_date DATE,
            description TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sites (
            site_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            extent TEXT,
            start_date DATE,
            previsional_end DATE,
            project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            deleted BOOLEAN DEFAULT FALSE,
            operating_rate DOUBLE PRECISION,
            main_site INTEGER
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS gateways (
            gateway_id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            serial_number TEXT,
            transfer_protocol TEXT,
            power_supply TEXT,
            installation_date DATE,
            x DOUBLE PRECISION, -- 用于存储经度 (Longitude)
            y DOUBLE PRECISION, -- 用于存储纬度 (Latitude)
            z DOUBLE PRECISION, -- 用于存储高度 (Altitude)
            time_zone TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS site_gateways (
            site_id INTEGER REFERENCES sites(site_id),
            gateway_id INTEGER REFERENCES gateways(gateway_id),
            PRIMARY KEY (site_id, gateway_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS configs (
            config_id SERIAL PRIMARY KEY,
            gateway_id INTEGER REFERENCES gateways(gateway_id),
            file_name TEXT,
            ftp_ip TEXT,
            regex_variables JSONB,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS raw_measurements (
            measurement_id BIGSERIAL PRIMARY KEY,
            variable_id INTEGER NOT NULL,
            sensor_id INTEGER,
            value DOUBLE PRECISION NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL
        );
        """,
        # 添加索引以优化查询性能
        "CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON raw_measurements (timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_measurements_variable_id ON raw_measurements (variable_id);"
    ]

    try:
        print(f"正在数据库 '{new_db}' 中初始化表结构...")
        for cmd in commands:
            cur.execute(cmd)
        conn.commit()
        print("所有表和索引初始化成功！项目已就绪。")
    except Exception as e:
        print(f"初始化表结构失败: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    setup_database()