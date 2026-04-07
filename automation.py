import json
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
import recurrence

def generate_tasks_for_client(client_id):
    conn = get_connection()
    try:
        client = pd.read_sql("SELECT * FROM clients WHERE client_id = ?", conn, params=(client_id,)).iloc[0]
        is_go = bool(client['go_flag'])
        is_gop = bool(client['gop_flag'])
    except:
        return 0
    
    df_standards = pd.read_sql("SELECT * FROM standards WHERE status = 'Active'", conn)
    
    # Grab all blueprints once for speed
    try:
        df_templates = pd.read_sql("SELECT * FROM task_templates", conn)
    except:
        df_templates = pd.DataFrame() # Fallback if table is somehow missing
    
    tasks_created = 0
    today = datetime.now()
    current_year = today.year
    
    conn_write = get_connection()
    c = conn_write.cursor()
    
    for code, group in df_standards.groupby('standard_code'):
        # 1. Check Standard Applicability
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
        
        # 2. Determine Deadlines
        rule = recurrence.get_recurrence_rule(code)
        generated_dates = recurrence.generate_dates(current_year, 10, rule)
        
        freq_label = rule[0].title()
        if freq_label == "Periodic":
            freq_label = f"Every {rule[1]} Years"
            
        # 3. Filter templates specifically for this standard
        std_templates = pd.DataFrame()
        if not df_templates.empty:
            std_templates = df_templates[df_templates['standard_code'] == code]
        
        for target_date in generated_dates:
            if target_date < today.date(): continue
            
            # --- SCENARIO A: WE HAVE BLUEPRINTS ---
            if not std_templates.empty:
                for _, temp in std_templates.iterrows():
                    # Check if this specific SUBTASK applies to the client
                    try: temp_tags = json.loads(temp['applicability_tags'])
                    except: temp_tags = []
                    
                    t_match = False
                    if is_go and 'GO' in temp_tags: t_match = True
                    if is_gop and 'GOP' in temp_tags: t_match = True
                    if not temp_tags: t_match = True # If no tags exist, apply it to everyone
                    
                    if t_match:
                        # Apply the blueprint's offset to the internal deadline
                        offset = int(temp['days_offset'])
                        internal_due = target_date - timedelta(days=offset)
                        
                        task_title = f"{code} - {temp['task_title']}"
                        description = f"Regulatory Target: {target_date.strftime('%Y-%m-%d')}"
                        
                        # Check idempotency (using TITLE now so we don't block multiple subtasks)
                        c.execute('''SELECT task_id FROM tasks WHERE client_id = ? AND standard_code = ? AND title = ? AND due_date = ?''', 
                                  (client_id, code, task_title, target_date))
                        
                        if not c.fetchone():
                            c.execute('''
                                INSERT INTO tasks (client_id, standard_code, title, description, due_date, internal_due_date, frequency, status, source, active_flag, priority, assigned_to)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Automation', 1, '🟡 Medium', 'Unassigned')
                            ''', (client_id, code, task_title, description, target_date, internal_due, freq_label))
                            tasks_created += 1

            # --- SCENARIO B: NO BLUEPRINTS (USE FALLBACK) ---
            else:
                internal_due = target_date - timedelta(days=30)
                rec_label = ""
                if rule[0] == 'quarterly': rec_label = f" (Q{(target_date.month-1)//3 + 1})"
                
                task_title = f"{code} - Compliance Review{rec_label} [{target_date.year}]"
                description = f"Requirements: {parts_str}"
                
                c.execute('''SELECT task_id FROM tasks WHERE client_id = ? AND standard_code = ? AND title = ? AND due_date = ?''', 
                          (client_id, code, task_title, target_date))
                
                if not c.fetchone():
                    c.execute('''
                        INSERT INTO tasks (client_id, standard_code, title, description, due_date, internal_due_date, frequency, status, source, active_flag, priority, assigned_to)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Automation', 1, '🟡 Medium', 'Unassigned')
                    ''', (client_id, code, task_title, description, target_date, internal_due, freq_label))
                    tasks_created += 1
    
    conn_write.commit()
    conn_write.close()
    conn.close()
    return tasks_created
