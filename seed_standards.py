import pandas as pd
import sqlite3
import json
import os

# --- CONFIGURATION ---
DB_PATH = "compliance_system.db"
EXCEL_FILENAME = "master.xlsx" # Streamlit saves the upload as this name

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
        raise FileNotFoundError("Could not find the uploaded file on the server.")

    # 2. BULLETPROOF FILE READING
    try:
        # Try reading as a true Excel file first
        df = pd.read_excel(EXCEL_FILENAME)
    except Exception as e1:
        try:
            # Fallback: Read as CSV if it's a CSV masquerading as an Excel file
            df = pd.read_csv(EXCEL_FILENAME, encoding='utf-8', encoding_errors='ignore')
        except Exception as e2:
            raise ValueError(f"Could not read file as Excel or CSV. \nExcel Error: {e1} \nCSV Error: {e2}")

    df.columns = df.columns.str.strip()
    
    # 3. VERIFY CRITICAL COLUMNS
    if 'Standard Version' not in df.columns and 'Standard' not in df.columns:
        raise KeyError(f"Missing Critical Column ('Standard Version' or 'Standard'). Columns found in your file: {list(df.columns)}")

    # 4. UPDATED FILTER LOGIC 
    if 'Status' in df.columns:
        df['Status_Clean'] = df['Status'].astype(str).str.strip().str.title()
        
        keep_statuses = [
            'Active', 
            'Subject To Enforcement', 
            'Mandatory Subject To Enforcement',
            'Subject To Future Enforcement'
        ]
        
        active_df = df[df['Status_Clean'].isin(keep_statuses)]
        
        if active_df.empty:
            raise ValueError(f"All {len(df)} rows were filtered out! The script only accepts Active or Enforced statuses. Statuses found in your file: {df['Status_Clean'].unique()}")
    else:
        active_df = df

    # 5. INSERT RECORDS
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
            pass # Skip exact duplicates

    conn.commit()
    conn.close()
    
    # Final safety check
    if count == 0:
        raise RuntimeError("Script executed, but zero records were inserted. Double-check your CSV formatting.")

if __name__ == "__main__":
    seed_database()
