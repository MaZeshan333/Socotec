import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load configuration
load_dotenv()

def get_connection(db_name):
    """Generic database connection helper function"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=db_name
    )

def setup_database():
    new_db = os.getenv("DB_NAME_NEW")
    
    # --- Step 1: Connect to the default 'postgres' database to create the new database ---
    conn = get_connection(os.getenv("DB_NAME_DEFAULT"))
    conn.autocommit = True  # Creating a database must run outside a transaction
    cur = conn.cursor()

    try:
        print(f"Creating database: {new_db}...")
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_db)))
        print(f"Database '{new_db}' created successfully!")
    except psycopg2.errors.DuplicateDatabase:
        print(f"Database '{new_db}' already exists, skipping creation.")
    except Exception as e:
        print(f"Database creation failed: {e}")
    finally:
        cur.close()
        conn.close()

    # --- Step 2: Connect to the newly created database and initialize table structures ---
    conn = get_connection(new_db)
    cur = conn.cursor()
    
    # All table creation statements (PostGIS GEOMETRY type removed)
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
            x DOUBLE PRECISION, -- Stores longitude
            y DOUBLE PRECISION, -- Stores latitude
            z DOUBLE PRECISION, -- Stores altitude
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
        # Add indexes to optimize query performance
        "CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON raw_measurements (timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_measurements_variable_id ON raw_measurements (variable_id);"
    ]

    try:
        print(f"Initializing table structures in database '{new_db}'...")
        for cmd in commands:
            cur.execute(cmd)
        conn.commit()
        print("All tables and indexes initialized successfully! Project is ready.")
    except Exception as e:
        print(f"Table structure initialization failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    setup_database()
