import pandas as pd
import json
import os
from database import get_connection

def parse_nerc_master(file_path):
    """
    Ingests the Master NERC Standards file.
    Maps columns: Standard Version -> code, GO/GOP cols -> applicability_tags
    Supports both CSV and Excel formats.
    """
    # 1. SMART READ: Check extension to decide how to open
    if file_path.endswith('.xlsx'):
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            print(f"Excel read error: {e}")
            return 0
    else:
        # If CSV, try UTF-8 first, then fallback to cp1252 (Windows default)
        try:
            df = pd.read_csv(file_path, low_memory=False, encoding='utf-8')
        except UnicodeDecodeError:
            print("UTF-8 failed, trying CP1252...")
            df = pd.read_csv(file_path, low_memory=False, encoding='cp1252')
    
    # 2. Filter for Active standards only
    # Ensure Status column exists and normalize
    if 'Status' in df.columns:
        df = df[df['Status'] == 'Active']
    
    conn = get_connection()
    c = conn.cursor()
    count = 0
    
    for _, row in df.iterrows():
        # 3. Extract Basic Info (with fallbacks)
        code = row.get('Standard Version', row.get('Standard')) # Fallback
        family = row.get('Family')
        req_text = row.get('Requirement Text')
        eff_date = row.get('Effective Date of Requirement')
        
        # 4. Determine Applicability (The Magic Logic)
        tags = []
        possible_roles = ['GO', 'GOP', 'BA', 'RC', 'TOP', 'TO', 'TSP']
        
        for role in possible_roles:
            if role in df.columns:
                val = str(row[role]).strip().upper()
                # If cell is not empty/nan and not "Inactive", it applies
                if val and val != 'NAN' and val != 'NAN' and val != 'INACTIVE' and val != 'nan':
                    tags.append(role)
        
        applicability_json = json.dumps(tags)
        
        # 5. Insert into DB (Upsert to avoid duplicates)
        try:
            # Only insert if we have a valid code
            if pd.notna(code):
                c.execute('''
                    INSERT INTO standards (standard_code, family, requirement_text, applicability_tags, effective_date, status)
                    VALUES (?, ?, ?, ?, ?, 'Active')
                    ON CONFLICT(standard_code) DO UPDATE SET
                    applicability_tags=excluded.applicability_tags,
                    status='Active'
                ''', (code, family, req_text, applicability_json, eff_date))
                count += 1
        except Exception as e:
            print(f"Error parsing {code}: {e}")
            
    conn.commit()
    conn.close()
    return count

def parse_client_details(file_path):
    """
    Reads Astra Wind 'Plant Details' to create a Client.
    """
    # Smart Read
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, header=None)
    else:
        try:
            df = pd.read_csv(file_path, header=None, encoding='utf-8')
        except:
            df = pd.read_csv(file_path, header=None, encoding='cp1252')
    
    client_name = "Unknown Client"
    go = 0
    gop = 0
    
    # Scan rows for keys
    for _, row in df.iterrows():
        row_str = " ".join([str(x) for x in row])
        
        if "Plant Name" in row_str:
            # Try to grab the value in the next column (col 1)
            try: client_name = row[1] 
            except: pass
            
        if "Registered as" in row_str:
            if "GO" in row_str or "Generator Owner" in row_str: go = 1
            if "GOP" in row_str or "Generator Operator" in row_str: gop = 1

    conn = get_connection()
    c = conn.cursor()
    
    # Default to generic name if parsing failed completely
    if pd.isna(client_name) or client_name == "nan":
        client_name = "New Client"

    print(f"Detected Client: {client_name} (GO: {go}, GOP: {gop})")

    c.execute('''
        INSERT INTO clients (client_name, go_flag, gop_flag)
        VALUES (?, ?, ?)
        ON CONFLICT(client_name) DO UPDATE SET
        go_flag=excluded.go_flag,
        gop_flag=excluded.gop_flag
    ''', (client_name, go, gop))
    conn.commit()
    
    # Return the ID
    c.execute("SELECT client_id FROM clients WHERE client_name=?", (client_name,))
    return c.fetchone()[0]

def parse_compliance_tracker(file_path, client_id):
    """
    Reads Astra Wind 'Compliance Tracking' to populate tasks.
    """
    # Smart Read
    if file_path.endswith('.xlsx'):
        df_raw = pd.read_excel(file_path, header=None, nrows=20)
    else:
        try:
            df_raw = pd.read_csv(file_path, header=None, nrows=20, encoding='utf-8')
        except:
            df_raw = pd.read_csv(file_path, header=None, nrows=20, encoding='cp1252')

    # Find header row
    header_idx = 0
    for idx, row in df_raw.iterrows():
        if "Task Details" in str(row.values):
            header_idx = idx
            break
            
    # Read full file with correct header
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, header=header_idx)
    else:
        try:
            df = pd.read_csv(file_path, header=header_idx, encoding='utf-8')
        except:
            df = pd.read_csv(file_path, header=header_idx, encoding='cp1252')
    
    conn = get_connection()
    c = conn.cursor()
    count = 0
    
    for _, row in df.iterrows():
        title = row.get('Task Details')
        if pd.isna(title): continue
        
        due_raw = row.get('Internal Due Date')
        status = row.get('Status', 'Pending')
        
        # Simple date cleaning
        try:
            if pd.notna(due_raw):
                due_date = pd.to_datetime(due_raw).date()
            else:
                due_date = None
        except:
            due_date = None
        
        c.execute('''
            INSERT INTO tasks (client_id, title, due_date, status, source)
            VALUES (?, ?, ?, ?, 'Legacy Import')
        ''', (client_id, title, due_date, status))
        count += 1
        
    conn.commit()
    return count