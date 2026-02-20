
import sys
import os
import csv
import psycopg2
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=Config.DB_CONFIG['dbname'],
            user=Config.DB_CONFIG['user'],
            password=Config.DB_CONFIG['password'],
            host=Config.DB_CONFIG['host'],
            port=Config.DB_CONFIG['port']
        )
        conn.autocommit = True
        return conn, conn.cursor()
    except Exception as e:
        print(f"❌ DB Connection Error: {e}")
        return None, None

def load_csv_to_table(csv_path, table_name, mapping=None):
    """
    Loads CSV data into a Postgres table.
    
    Args:
        csv_path (str): Path to the CSV file.
        table_name (str): Target table name (e.g., 'rdb_transfers').
        mapping (dict): Optional column mapping {csv_col: db_col}. If None, assumes matching names.
    """
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return

    conn, cur = get_db_connection()
    if not conn: return

    try:
        print(f"🚀 Loading {csv_path} into table '{table_name}'...")
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            # Prepare SQL
            # If mapping provided, use it. Else use CSV headers directly (must match DB columns)
            if mapping:
                db_cols = [mapping.get(h, h) for h in headers]
            else:
                db_cols = headers
                
            cols_str = ", ".join(db_cols)
            placeholders = ", ".join(["%s"] * len(db_cols))
            
            insert_query = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            
            count = 0
            for row in reader:
                values = [row[h] for h in headers]
                # Basic data cleaning (empty string -> None)
                cleaned_values = [v if v.strip() != '' else None for v in values]
                
                try:
                    cur.execute(insert_query, cleaned_values)
                    count += 1
                except Exception as row_err:
                    print(f"   ⚠ Row Error: {row_err} | Data: {values}")
            
            print(f"✅ Successfully loaded {count} rows into '{table_name}'.")

    except Exception as e:
        print(f"❌ Load Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Load CSV to RDB Table')
    parser.add_argument('csv_path', help='Path to CSV file')
    parser.add_argument('table_name', help='Target DB table name (e.g. rdb_transfers)')
    
    args = parser.parse_args()
    
    load_csv_to_table(args.csv_path, args.table_name)
