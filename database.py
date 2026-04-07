import sqlite3
import os

DB_PATH = "compliance_system.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Create Clients Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            client_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            go_flag INTEGER DEFAULT 0,
            gop_flag INTEGER DEFAULT 0,
            regional_entity TEXT,
            active_flag INTEGER DEFAULT 1
        )
    ''')
    
    # Create Tasks Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            standard_code TEXT,
            title TEXT,
            description TEXT,
            due_date DATE,
            internal_due_date DATE,
            frequency TEXT DEFAULT 'Annual',
            priority TEXT DEFAULT '🟡 Medium',
            assigned_to TEXT DEFAULT 'Unassigned',
            status TEXT DEFAULT 'Pending',
            source TEXT,
            active_flag INTEGER DEFAULT 1,
            FOREIGN KEY (client_id) REFERENCES clients (client_id)
        )
    ''')
    
    # Create Standards Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS standards (
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

    # --- NEW: Task Templates (Blueprints) ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS task_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_code TEXT NOT NULL,
            task_title TEXT NOT NULL,
            applicability_tags TEXT,
            days_offset INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
