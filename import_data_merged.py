import os
import glob
import io
import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# 1. Load configuration from .env file
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME_DEFAULT = os.getenv("DB_NAME_DEFAULT")
DB_NAME_NEW = os.getenv("DB_NAME_NEW")

def get_connection(db_name):
    """Establishes a connection to the specified database."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=db_name
    )

def create_target_database():
    """Drops the target database if it exists (forcing disconnection) and creates a fresh one."""
    conn = get_connection(DB_NAME_DEFAULT)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Check if the database already exists
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s;", (DB_NAME_NEW,))
    exists = cursor.fetchone()
    
    if exists:
        print(f"Database '{DB_NAME_NEW}' already exists. Terminating active connections and dropping it...")
        try:
            # Force close all other active connections to this database to avoid lock errors
            cursor.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{DB_NAME_NEW}'
                  AND pid <> pg_backend_pid();
            """)
        except Exception as e:
            print(f"Notice while disconnecting active sessions: {e}")
            
        cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(DB_NAME_NEW)))
        print("Old database dropped successfully.")
        
    print(f"Creating a brand new database: '{DB_NAME_NEW}'...")
    cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME_NEW)))
    print("Database created successfully!")
        
    cursor.close()
    conn.close()

def create_tables(cursor):
    """Creates the database tables with all original columns in order of relational dependency."""
    print("Initializing table structures...")
    
    # 1. Projects table (from projects_sites.csv)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INT PRIMARY KEY,
            name VARCHAR(255),
            country VARCHAR(255),
            client_company_name VARCHAR(255),
            time_zone VARCHAR(255),
            city VARCHAR(255),
            start_date VARCHAR(255),
            description TEXT
        );
    """)
    
    # 2. Sites table (from projects_sites.csv)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id_1 INT PRIMARY KEY,
            name_2 VARCHAR(255),
            type VARCHAR(255),
            extent VARCHAR(255),
            start_date_3 VARCHAR(255),
            previsional_end VARCHAR(255),
            project_id INT REFERENCES projects(id),
            created_at VARCHAR(255),
            updated_at VARCHAR(255),
            deleted VARCHAR(255),
            operating_rate DOUBLE PRECISION,
            main_site DOUBLE PRECISION
        );
    """)

    # 3. Gateways table (from gateways_configs_sensors.csv)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gateways (
            id INT PRIMARY KEY,
            gateway_name VARCHAR(255),
            serial_number VARCHAR(255),
            transfer_protocol VARCHAR(255),
            power_supply VARCHAR(255),
            installation_date VARCHAR(255),
            operating_team VARCHAR(255),
            x DOUBLE PRECISION,
            y DOUBLE PRECISION,
            z DOUBLE PRECISION,
            time_zone VARCHAR(255),
            geom TEXT,
            created_at VARCHAR(255),
            updated_at VARCHAR(255),
            provider INT,
            site_id INT REFERENCES sites(id_1)
        );
    """)

    # 4. Configs table (from gateways_configs_sensors.csv)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configs (
            id_1 INT PRIMARY KEY,
            file_name VARCHAR(255),
            last_treatment VARCHAR(255),
            ftp VARCHAR(255),
            ftp_ip VARCHAR(255),
            ftp_user VARCHAR(255),
            ftp_password VARCHAR(255),
            ftp_directory TEXT,
            config TEXT,
            gateway_id INT REFERENCES gateways(id),
            parsing_id INT,
            file_id DOUBLE PRECISION,
            to_move BOOLEAN,
            regex_variables TEXT,
            created_at_1 VARCHAR(255),
            updated_at_1 VARCHAR(255),
            active BOOLEAN,
            error_message TEXT,
            last_modified VARCHAR(255),
            keep_folder DOUBLE PRECISION
        );
    """)

    # 5. Raw Data table (from variables_metrics_raw_data-*.csv)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS variables_metrics_raw_data (
            gateway_name VARCHAR(255),
            variable_name VARCHAR(255),
            variable_alias VARCHAR(255),
            sensor_id INT,
            value DOUBLE PRECISION,
            timestamp VARCHAR(255),
            variable_id INT,
            unit VARCHAR(255),
            metric VARCHAR(255)
        );
    """)
    print("All tables and column schemas created successfully.")

def fast_copy_dataframe(cursor, df, table_name, columns):
    """Saves DataFrame into an in-memory StringIO buffer and uses COPY for high-speed migration."""
    df_filtered = df[columns].copy()
    
    output = io.StringIO()
    df_filtered.to_csv(output, sep='\t', index=False, header=False, na_rep='\\N')
    output.seek(0)
    
    cursor.copy_from(output, table_name, null='\\N', columns=columns)
    print(f"Successfully imported {len(df_filtered)} rows into table: {table_name}")

def import_data(cursor):
    """Reads source CSV files, extracts up to 30 unique rows per entity, and performs bulk inserts."""
    
    # ---------------------------------------------
    # 1. Processing projects_sites.csv (Semicolon Sep)
    # ---------------------------------------------
    print("\nProcessing 'projects_sites.csv'...")
    # Added encoding='latin-1' to handle special French characters safely
    df_ps = pd.read_csv("projects_sites.csv", sep=';', encoding='latin-1')
    
    # Extract unique projects and limit to the first 30 rows
    project_cols = ['id', 'name', 'country', 'client_company_name', 'time_zone', 'city', 'start_date', 'description']
    df_projects = df_ps[project_cols].drop_duplicates(subset=['id']).head(30)
    fast_copy_dataframe(cursor, df_projects, 'projects', project_cols)
    
    # Extract unique sites and limit to the first 30 rows
    site_cols = ['id_1', 'name_2', 'type', 'extent', 'start_date_3', 'previsional_end', 'project_id', 'created_at', 'updated_at', 'deleted', 'operating_rate', 'main_site']
    df_sites = df_ps[site_cols].drop_duplicates(subset=['id_1']).head(30)
    fast_copy_dataframe(cursor, df_sites, 'sites', site_cols)

    # ---------------------------------------------
    # 2. Processing gateways_configs_sensors.csv (Comma Sep)
    # ---------------------------------------------
    print("\nProcessing 'gateways_configs_sensors.csv'...")
    # Added encoding='latin-1' just in case this file contains special characters too
    df_gcs = pd.read_csv("gateways_configs_sensors.csv", encoding='latin-1')
    
    # Clean column headers (replace "." with "_" to comply with PostgreSQL naming standards)
    df_gcs.columns = [c.replace('.', '_') for c in df_gcs.columns]
    
    # Extract unique gateways, remap 'id_2' as 'site_id' to build relation, limit to 30 rows
    gateway_cols = ['id', 'gateway_name', 'serial_number', 'transfer_protocol', 'power_supply', 'installation_date', 'operating_team', 'x', 'y', 'z', 'time_zone', 'geom', 'created_at', 'updated_at', 'provider']
    df_gateways_to_import = df_gcs[gateway_cols + ['id_2']].copy()
    df_gateways_to_import = df_gateways_to_import.rename(columns={'id_2': 'site_id'})
    df_gateways_to_import = df_gateways_to_import.drop_duplicates(subset=['id']).head(30)
    fast_copy_dataframe(cursor, df_gateways_to_import, 'gateways', gateway_cols + ['site_id'])

    # Extract unique configs and limit to the first 30 rows
    config_cols = ['id_1', 'file_name', 'last_treatment', 'ftp', 'ftp_ip', 'ftp_user', 'ftp_password', 'ftp_directory', 'config', 'gateway_id', 'parsing_id', 'file_id', 'to_move', 'regex_variables', 'created_at_1', 'updated_at_1', 'active', 'error_message', 'last_modified', 'keep_folder']
    df_configs = df_gcs[config_cols].drop_duplicates(subset=['id_1']).head(30)
    fast_copy_dataframe(cursor, df_configs, 'configs', config_cols)

    # ---------------------------------------------
    # 3. Processing variables_metrics_raw_data-*.csv
    # ---------------------------------------------
    raw_data_files = glob.glob("variables_metrics_raw_data-*.csv")
    if not raw_data_files:
        print("\n[Warning] Could not find any file matching 'variables_metrics_raw_data-*.csv'. Skipping.")
        return
        
    print(f"\nProcessing '{raw_data_files[0]}'...")
    df_rd = pd.read_csv(raw_data_files[0], encoding='latin-1')
    
    # Extract all 9 metric data columns and limit to the first 30 sequential log entries
    raw_cols = ['gateway_name', 'variable_name', 'variable_alias', 'sensor_id', 'value', 'timestamp', 'variable_id', 'unit', 'metric']
    df_raw_limited = df_rd[raw_cols].head(30)
    fast_copy_dataframe(cursor, df_raw_limited, 'variables_metrics_raw_data', raw_cols)

def main():
    try:
        # Step 1: Drop old database if present and build a completely clean context
        create_target_database()
        
        # Step 2: Connect to the newly configured database to execute table build and pipeline
        print(f"\nConnecting to the fresh target database: '{DB_NAME_NEW}'...")
        conn = get_connection(DB_NAME_NEW)
        cursor = conn.cursor()
        
        # Build Tables
        create_tables(cursor)
        
        # Populate Limited Datasets
        import_data(cursor)
        
        # Commit transactional changes
        conn.commit()
        print("\n[Success] Database rebuilt cleanly and first 30 rows imported for each table successfully!")
        
    except Exception as e:
        print(f"\n[Error] Execution failed due to runtime exception: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            print("Transaction rolled back successfully.")
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()
