import sqlite3

DB_PATH = "compliance_system.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # 1. CLIENTS TABLE
    c.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            client_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL UNIQUE,
            go_flag INTEGER DEFAULT 0,
            gop_flag INTEGER DEFAULT 0,
            regional_entity TEXT,
            active_flag INTEGER DEFAULT 1
        )
    ''')

    # 2. STANDARDS TABLE (Matching your seeded schema)
    c.execute('''
        CREATE TABLE IF NOT EXISTS standards (
            standard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_code TEXT NOT NULL,
            family TEXT,
            sub_section TEXT,
            requirement_text TEXT,
            applicability_tags TEXT,
            effective_date DATE,
            status TEXT,
            UNIQUE(standard_code, sub_section)
        )
    ''')

    # 3. TASKS TABLE
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            standard_id INTEGER,
            title TEXT NOT NULL,
            due_date DATE,
            status TEXT DEFAULT 'Pending',
            source TEXT DEFAULT 'Manual',
            active_flag INTEGER DEFAULT 1,
            FOREIGN KEY (client_id) REFERENCES clients(client_id),
            FOREIGN KEY (standard_id) REFERENCES standards(standard_id)
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()