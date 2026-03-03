import json
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
import recurrence

def generate_tasks_for_client(client_id):
    """
    Level 5 Automation: V3 SCHEMA AWARE
    1. Fetches requirements.
    2. Groups by Standard.
    3. Looks up Recurrence Rule.
    4. Generates both Regulatory and Internal (-30 Days) deadlines.
    5. Populates all V3 columns (frequency, active_flag).
    """
    conn = get_connection()
    
    try:
        client = pd.read_sql("SELECT * FROM clients WHERE client_id = ?", conn, params=(client_id,)).iloc[0]
        is_go = bool(client['go_flag'])
        is_gop = bool(client['gop_flag'])
    except:
        return 0
    
    df = pd.read_sql("SELECT * FROM standards WHERE status = 'Active'", conn)
    tasks_created = 0
    today = datetime.now()
    current_year = today.year
    
    for code, group in df.groupby('standard_code'):
        # Check Applicability
        applicable_parts = []
        for _, row in group.iterrows():
            try: tags = json.loads(row['applicability_tags'])
            except: tags = []
            
            match = False
            if is_go and 'GO' in tags: match = True
            if is_gop and 'GOP' in tags: match = True
            if match:
                part = row['sub_section'] if row['sub_section'] else "Main"
                applicable_parts.append(part)
        
        if not applicable_parts: continue
        parts_str = ", ".join(sorted(list(set(applicable_parts))))
        
        # Pull from recurrence.py
        rule = recurrence.get_recurrence_rule(code)
        generated_dates = recurrence.generate_dates(current_year, 10, rule)
        
        # Format Frequency Label for UI
        freq_label = rule[0].title()
        if freq_label == "Periodic":
            freq_label = f"Every {rule[1]} Years"
            
        conn_write = get_connection()
        c = conn_write.cursor()
        
        for due_date in generated_dates:
            if due_date < today.date(): continue
            
            # Auto-Calculate Internal Deadline
            internal_due = due_date - timedelta(days=30)
            
            rec_label = ""
            if rule[0] == 'quarterly': rec_label = f" (Q{(due_date.month-1)//3 + 1})"
            
            task_title = f"{code} - Compliance Review{rec_label} [{due_date.year}]"
            description = f"Requirements: {parts_str}"
            
            # Idempotency Check
            c.execute('''
                SELECT task_id FROM tasks 
                WHERE client_id = ? AND standard_code = ? AND due_date = ?
            ''', (client_id, code, due_date))
            
            if not c.fetchone():
                c.execute('''
                    INSERT INTO tasks (
                        client_id, standard_code, title, description, 
                        due_date, internal_due_date, frequency, 
                        status, source, active_flag, priority, assigned_to
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Automation', 1, '🟡 Medium', 'Unassigned')
                ''', (client_id, code, task_title, description, due_date, internal_due, freq_label))
                tasks_created += 1
        
        conn_write.commit()
        conn_write.close()
    conn.close()
    return tasks_created