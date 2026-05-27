import pandas as pd
import os

ORIGIN_DIR = 'Origin'
NEW_DIR = 'New'

if not os.path.exists(NEW_DIR):
    os.makedirs(NEW_DIR)

def clean_data():
    print("Starting data extraction and cleaning from Origin...")
    ENCODING = 'ISO-8859-1' 

    # Load original files
    df_ps = pd.read_csv(os.path.join(ORIGIN_DIR, 'projects_sites.csv'), sep=';', encoding=ENCODING)
    df_gcs = pd.read_csv(os.path.join(ORIGIN_DIR, 'gateways_configs_sensors.csv'), encoding=ENCODING)
    
    raw_files = [f for f in os.listdir(ORIGIN_DIR) if f.startswith('variables_metrics_raw_data')]
    df_raw = pd.read_csv(os.path.join(ORIGIN_DIR, raw_files[0]), encoding=ENCODING)

    def to_int(df, columns):
        for col in columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
        return df

    # 1. Projects
    projects = df_ps[['id', 'name', 'country', 'client_company_name', 'time_zone', 'city', 'start_date', 'description']].drop_duplicates()
    projects.columns = ['project_id', 'name', 'country', 'client_company_name', 'time_zone', 'city', 'start_date', 'description']
    projects = to_int(projects, ['project_id'])
    projects.to_csv(os.path.join(NEW_DIR, 'projects.csv'), index=False, encoding='utf-8')

    # 2. Sites
    sites = df_ps[['id_1', 'name_2', 'type', 'extent', 'start_date_3', 'previsional_end', 'project_id', 'created_at', 'updated_at', 'deleted', 'operating_rate', 'main_site']].drop_duplicates()
    sites.columns = ['site_id', 'name', 'type', 'extent', 'start_date', 'previsional_end', 'project_id', 'created_at', 'updated_at', 'deleted', 'operating_rate', 'main_site']
    sites['deleted'] = sites['deleted'].astype(str).str.upper().map({'FAUX': False, 'VRAI': True, 'FALSE': False, 'TRUE': True, 'NAN': False})
    sites = to_int(sites, ['site_id', 'project_id', 'main_site'])
    sites.to_csv(os.path.join(NEW_DIR, 'sites.csv'), index=False, encoding='utf-8')

    # 3. Gateways (based on gateways_configs_sensors.csv structure)
    gateways = df_gcs.iloc[:, 0:15].drop_duplicates()
    gateways = gateways[gateways.iloc[:, 0].notna()]
    gateways_final = pd.DataFrame({
        'gateway_id': gateways.iloc[:, 0], 'name': gateways.iloc[:, 1],
        'serial_number': gateways.iloc[:, 2], 'transfer_protocol': gateways.iloc[:, 3],
        'power_supply': gateways.iloc[:, 4], 'installation_date': gateways.iloc[:, 5],
        'x': gateways.iloc[:, 7], 'y': gateways.iloc[:, 8], 'z': gateways.iloc[:, 9],
        'time_zone': gateways.iloc[:, 10], 'created_at': gateways.iloc[:, 12]
    })
    gateways_final = to_int(gateways_final, ['gateway_id'])
    gateways_final.to_csv(os.path.join(NEW_DIR, 'gateways.csv'), index=False, encoding='utf-8')

    # 4. Site_Gateways
    site_id_col = [col for col in df_gcs.columns if col.startswith('id')][-1]
    gw_id_col = df_gcs.columns[0]
    site_gateways = df_gcs[[site_id_col, gw_id_col]].drop_duplicates().dropna()
    site_gateways.columns = ['site_id', 'gateway_id']
    site_gateways = to_int(site_gateways, ['site_id', 'gateway_id'])
    site_gateways.to_csv(os.path.join(NEW_DIR, 'site_gateways.csv'), index=False, encoding='utf-8')

    # 5. Configs
    configs = df_gcs.iloc[:, 15:35].drop_duplicates()
    configs_final = pd.DataFrame({
        'config_id': configs.iloc[:, 0], 'gateway_id': configs.iloc[:, 9],
        'file_name': configs.iloc[:, 1], 'ftp_ip': configs.iloc[:, 4],
        'regex_variables': configs.iloc[:, 13], 'active': configs.iloc[:, 16],
        'created_at': configs.iloc[:, 14]
    })
    configs_final['active'] = configs_final['active'].astype(str).str.upper().map({'TRUE': True, 'VRAI': True, 'FALSE': False, 'FAUX': False})
    configs_final = to_int(configs_final, ['config_id', 'gateway_id'])
    configs_final.to_csv(os.path.join(NEW_DIR, 'configs.csv'), index=False, encoding='utf-8')

    # 6. Raw Measurements (key fix)
    # Remove rows with empty value, otherwise database import will error
    raw_m = df_raw[['variable_id', 'sensor_id', 'value', 'timestamp']].drop_duplicates()
    raw_m = raw_m.dropna(subset=['value']) 
    raw_m = to_int(raw_m, ['variable_id', 'sensor_id'])
    raw_m.to_csv(os.path.join(NEW_DIR, 'raw_measurements.csv'), index=False, encoding='utf-8')

    print(f"Cleaning complete! All files saved to {NEW_DIR}.")

if __name__ == "__main__":
    clean_data()
