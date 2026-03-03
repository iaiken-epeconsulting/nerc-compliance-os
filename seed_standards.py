import pandas as pd
import sqlite3
import json
import os

# --- CONFIGURATION ---
DB_PATH = "compliance_system.db"
EXCEL_FILENAME = "master.xlsx"

def sanitize(val):
    if pd.isna(val): return None
    if isinstance(val, (pd.Timestamp, pd.DatetimeIndex)): return val.strftime('%Y-%m-%d')
    return str(val).strip()

def seed_database():
    print(f"--- STARTING DATABASE SEED ---")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. RESET SCHEMA 
    c.execute("DROP TABLE IF EXISTS standards")
    
    c.execute('''
        CREATE TABLE standards (
            standard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_code TEXT NOT NULL,
            family TEXT,
            sub_section TEXT,                  
            title TEXT,
            requirement_text TEXT,
            applicability_tags TEXT,
            effective_date DATE,
            status TEXT DEFAULT 'Active',
            UNIQUE(standard_code, sub_section) 
        )
    ''')

    if not os.path.exists(EXCEL_FILENAME):
        print(f"ERROR: Could not find {EXCEL_FILENAME}")
        return

    print(f"Reading {EXCEL_FILENAME}...")
    try:
        df = pd.read_excel(EXCEL_FILENAME)
    except Exception as e:
        print(f"Read Error: {e}")
        return

    df.columns = df.columns.str.strip()
    
    # 2. UPDATED FILTER LOGIC (Catches your exact NERC terms)
    if 'Status' in df.columns:
        df['Status_Clean'] = df['Status'].astype(str).str.strip().str.title()
        
        # We now explicitly look for these exact phrases from your sheet
        keep_statuses = [
            'Active', 
            'Subject To Enforcement', 
            'Mandatory Subject To Enforcement',
            'Subject To Future Enforcement'
        ]
        
        active_df = df[df['Status_Clean'].isin(keep_statuses)]
        print(f"Filter kept {len(active_df)} rows (out of {len(df)} total).")
    else:
        active_df = df

    print("Inserting records...")
    count = 0
    
    for idx, row in active_df.iterrows():
        code = row.get('Standard Version')
        if pd.isna(code): code = row.get('Standard')
        if pd.isna(code): continue

        code_str = sanitize(code)
        family_str = sanitize(row.get('Family'))
        
        sub_section_str = sanitize(row.get('Requirement / Part'))
        if not sub_section_str:
            sub_section_str = "General"

        req_str = sanitize(row.get('Requirement Text'))
        eff_date_str = sanitize(row.get('Effective Date of Requirement'))
        
        tags = []
        possible_roles = ['GO', 'GOP', 'BA', 'RC', 'TOP', 'TO', 'TSP']
        for role in possible_roles:
            if role in df.columns:
                val = str(row[role]).strip().upper()
                if val and val not in ['NAN', 'NO', '', 'INACTIVE', 'NONE']:
                    tags.append(role)
        tags_json = json.dumps(tags)

        try:
            c.execute('''
                INSERT INTO standards (
                    standard_code, family, sub_section, requirement_text, 
                    applicability_tags, effective_date, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'Active')
            ''', (code_str, family_str, sub_section_str, req_str, tags_json, eff_date_str))
            count += 1
        except sqlite3.IntegrityError:
            pass
        except Exception as e:
            print(f"Error on {code_str}: {e}")

    conn.commit()
    conn.close()
    print(f"--- SUCCESS ---")
    print(f"Database populated with {count} rows.")

if __name__ == "__main__":
    seed_database()
