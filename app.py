import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# Local modules
from database import init_db, get_connection
import parsers
import automation
import reports

# --- CONFIGURATION & THEME ---
st.set_page_config(page_title="NERC Manager", page_icon="⚡", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f4f6f9; color: #000000 !important; }
    h1, h2, h3, h4, h5, h6, p, li, span, div, label { color: #000000 !important; }
    .css-1r6slb0, .css-12oz5g7, [data-testid="stExpander"], [data-testid="stForm"] {
        background-color: #ffffff !important; border: 1px solid #d0d0d0; border-radius: 8px;
    }
    input, textarea, select { color: #000000 !important; background-color: #ffffff !important; }
    .stTextInput > div > div, .stDateInput > div > div, .stSelectbox > div > div {
        background-color: #ffffff !important; border: 1px solid #888888 !important; color: #000000 !important;
    }
    [data-testid="stDataFrame"] { background-color: #ffffff !important; border: 1px solid #e0e0e0; border-radius: 8px; }
    div[data-baseweb="popover"], div[data-baseweb="menu"], div[role="listbox"] {
        background-color: #ffffff !important; border: 1px solid #d0d0d0 !important;
    }
    div[data-baseweb="popover"] * { color: #000000 !important; background-color: #ffffff !important; }
    .monday-card {
        background-color: white; padding: 20px; border-radius: 8px; border-left: 6px solid #6c63ff; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align: center; border: 1px solid #d0d0d0;
    }
    [data-testid="stSidebar"] { background-color: #202538 !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    
    /* Red button styling for Danger Zone */
    button[kind="primary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

if not os.path.exists("data"): os.makedirs("data")
if 'db_setup' not in st.session_state:
    init_db()
    st.session_state['db_setup'] = True

# Standard Configuration
USER_LIST = ["Unassigned", "Ian Aiken", "Compliance Team", "Engineering Dept", "Management"]
FREQ_LIST = ["Annual", "Quarterly", "Monthly", "Weekly", "Event-Driven", "One-Time"]

# --- HELPERS ---
def run_query(query, params=None):
    conn = get_connection()
    try: return pd.read_sql(query, conn, params=params) if params else pd.read_sql(query, conn)
    finally: conn.close()

def execute_command(sql, params):
    conn = get_connection()
    try: conn.execute(sql, params); conn.commit()
    finally: conn.close()

# --- SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=50)
st.sidebar.title("NERC OS")
page = st.sidebar.radio("Workspace", ["Dashboard", "My Tasks", "Clients", "Standards Library"])
st.sidebar.divider()
st.sidebar.info("v3.1 | Beta Sandbox Edition")

# --- DASHBOARD ---
if page == "Dashboard":
    st.title("Executive Dashboard")
    st.markdown("Welcome to the NERC Compliance Tester. Please review the tabs on the left to navigate assets and tasks.")
    st.divider()
    
    try:
        task_counts = run_query("SELECT status, COUNT(*) as count FROM tasks WHERE active_flag=1 GROUP BY status")
        total = task_counts['count'].sum() if not task_counts.empty else 0
        pending = task_counts[task_counts['status'] == 'Pending']['count'].sum() if not task_counts.empty else 0
        
        next_90 = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        upcoming = run_query(f"SELECT COUNT(*) as count FROM tasks WHERE internal_due_date <= '{next_90}' AND status != 'Completed' AND active_flag=1").iloc[0]['count']
        client_count = run_query("SELECT COUNT(*) as count FROM clients WHERE active_flag=1").iloc[0]['count']

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f"""<div class="monday-card" style="border-left-color: #00c875;"><h3>Active Tasks</h3><h2>{total}</h2></div>""", unsafe_allow_html=True)
        with c2: st.markdown(f"""<div class="monday-card" style="border-left-color: #fdab3d;"><h3>Pending Actions</h3><h2>{pending}</h2></div>""", unsafe_allow_html=True)
        with c3: st.markdown(f"""<div class="monday-card" style="border-left-color: #ff5ac8;"><h3>Due Next 90 Days</h3><h2>{upcoming}</h2></div>""", unsafe_allow_html=True)
        with c4: st.markdown(f"""<div class="monday-card" style="border-left-color: #579bfc;"><h3>Active Clients</h3><h2>{client_count}</h2></div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Data Error: {e}")

    st.subheader("⚠️ Critical Attention Board")
    critical_df = run_query(f"""
        SELECT t.task_id, c.client_name, t.title, t.internal_due_date, t.due_date, t.priority, t.status 
        FROM tasks t 
        JOIN clients c ON t.client_id = c.client_id 
        WHERE t.status != 'Completed' AND t.internal_due_date <= '{next_90}' AND t.active_flag=1
        ORDER BY t.internal_due_date ASC 
        LIMIT 10
    """)
    if not critical_df.empty:
        st.dataframe(
            critical_df, use_container_width=True, hide_index=True,
            column_config={
                "status": st.column_config.TextColumn("Status"),
                "internal_due_date": st.column_config.DateColumn("Internal Target", format="MMM DD, YYYY"),
                "due_date": st.column_config.DateColumn("Regulatory Deadline", format="MMM DD, YYYY"),
                "title": st.column_config.TextColumn("Task Name", width="large"),
                "priority": st.column_config.TextColumn("Urgency")
            }
        )
    else:
        st.success("All caught up! No critical deadlines.")

# --- TASKS ---
elif page == "My Tasks":
    st.title("Board: Compliance Tasks")
    st.caption("💡 To delete a task, click the gray box on the far left of the row, click the trash can, and hit 'Save Changes'.")
    
    # --- TASK CREATION FORM (WITH VALIDATION) ---
    with st.expander("➕ New Custom Task"):
        with st.form("quick_add"):
            st.write("Add Ad-Hoc Task")
            client_list = run_query("SELECT client_name FROM clients")['client_name'].tolist()
            if client_list:
                c1, c2, c3 = st.columns(3)
                qa_client = c1.selectbox("Client", client_list)
                qa_title = c2.text_input("Task Name")
                qa_date = c3.date_input("Regulatory Deadline")
                
                c4, c5, c6 = st.columns(3)
                qa_priority = c4.selectbox("Urgency", ["🔴 High", "🟡 Medium", "🟢 Low"])
                qa_assignee = c5.selectbox("Assignee", USER_LIST)
                qa_freq = c6.selectbox("Frequency", FREQ_LIST)
                
                if st.form_submit_button("Add to Board"):
                    if not qa_title.strip():
                        st.error("⚠️ Please enter a Task Name before submitting.")
                    else:
                        cid = run_query("SELECT client_id FROM clients WHERE client_name=?", (qa_client,)).iloc[0]['client_id']
                        internal_target = qa_date - timedelta(days=30)
                        
                        execute_command(
                            "INSERT INTO tasks (client_id, title, due_date, internal_due_date, priority, assigned_to, frequency, status, source, active_flag) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Manual', 1)", 
                            (int(cid), qa_title, qa_date, internal_target, qa_priority, qa_assignee, qa_freq)
                        )
                        st.success("Added! Internal deadline auto-set to 30 days prior."); st.rerun()
            else: st.warning("Create a client first!")

    st.divider()

    # --- FILTERS ---
    f1, f2, f3, f4 = st.columns(4)
    with f1: 
        client_opts = ["All"] + run_query("SELECT client_name FROM clients")['client_name'].tolist()
        filter_asset = st.selectbox("Filter Asset", client_opts)
    with f2: filter_user = st.selectbox("Assignee", ["All"] + USER_LIST)
    with f3: filter_status = st.selectbox("Status", ["All", "Pending", "In Progress", "Completed"])
    with f4: search = st.text_input("Search", placeholder="Type to search...")

    # --- QUERY ---
    base_query = """
        SELECT t.task_id, c.client_name, t.title, t.description, t.internal_due_date, t.due_date, t.frequency, t.priority, t.assigned_to, t.status 
        FROM tasks t 
        JOIN clients c ON t.client_id = c.client_id
        WHERE t.active_flag = 1
    """
    params = []
    if filter_asset != "All":
        base_query += " AND c.client_name = ?"; params.append(filter_asset)
    if filter_status != "All":
        base_query += " AND t.status = ?"; params.append(filter_status)
    if filter_user != "All":
        base_query += " AND t.assigned_to = ?"; params.append(filter_user)
    if search:
        base_query += f" AND t.title LIKE '%{search}%'"
    
    df = run_query(base_query + " ORDER BY t.internal_due_date ASC", params)
    
    if df.empty:
        st.info("No tasks found matching your filters.")
    else:
        df['priority'] = df['priority'].fillna("🟡 Medium")
        df['assigned_to'] = df['assigned_to'].fillna("Unassigned")
        df['frequency'] = df['frequency'].fillna("Annual")
        df['due_date'] = pd.to_datetime(df['due_date'], errors='coerce')
        df['internal_due_date'] = pd.to_datetime(df['internal_due_date'], errors='coerce')

        # --- DYNAMIC DATA EDITOR (ENABLES DELETION) ---
        edited_df = st.data_editor(
            df, key="task_editor", disabled=["task_id", "client_name"],
            num_rows="dynamic", # <--- THIS ENABLES ROW DELETION
            column_config={
                "title": st.column_config.TextColumn("Task Name", width="large", required=True),
                "client_name": st.column_config.TextColumn("Asset", width="medium"),
                "description": st.column_config.TextColumn("Notes", width="small"),
                "internal_due_date": st.column_config.DateColumn("Internal Target", format="MMM DD, YYYY"),
                "due_date": st.column_config.DateColumn("Regulatory Deadline", format="MMM DD, YYYY"),
                "frequency": st.column_config.SelectboxColumn("Cycle", options=FREQ_LIST, width="small"),
                "priority": st.column_config.SelectboxColumn("Urgency", options=["🔴 High", "🟡 Medium", "🟢 Low"], width="small", required=True),
                "assigned_to": st.column_config.SelectboxColumn("Assignee", options=USER_LIST, width="small"),
                "status": st.column_config.SelectboxColumn("Status", options=["Pending", "In Progress", "Completed", "Deferred"], width="small", required=True)
            },
            use_container_width=True, hide_index=False # Show index so users can click to delete
        )

        if st.button("💾 Save Changes", type="primary"):
            conn = get_connection()
            c = conn.cursor()
            
            # 1. PROCESS DELETIONS
            # If a task ID exists in the original DB but not in the editor, it was deleted.
            original_ids = set(df['task_id'].dropna())
            remaining_ids = set(edited_df['task_id'].dropna())
            deleted_ids = original_ids - remaining_ids
            
            for tid in deleted_ids:
                c.execute("DELETE FROM tasks WHERE task_id = ?", (int(tid),))
            
            # 2. PROCESS UPDATES
            for index, row in edited_df.dropna(subset=['task_id']).iterrows():
                save_date = row['due_date'].date() if pd.notnull(row['due_date']) else None
                internal_date = row['internal_due_date'].date() if pd.notnull(row['internal_due_date']) else None
                
                c.execute(
                    """UPDATE tasks 
                       SET status=?, due_date=?, internal_due_date=?, description=?, title=?, priority=?, assigned_to=?, frequency=? 
                       WHERE task_id=?""", 
                    (row['status'], save_date, internal_date, row['description'], row['title'], row['priority'], row['assigned_to'], row['frequency'], row['task_id'])
                )
            conn.commit(); conn.close()
            st.success(f"Board updated! ({len(deleted_ids)} deleted)."); st.rerun()

# --- CLIENTS ---
elif page == "Clients":
    st.title("Client Registry")
    
    with st.expander("➕ Register New Asset / Client", expanded=False):
        with st.form("new_client_form"):
            st.write("Add a new Generation Asset or Client.")
            new_client_name = st.text_input("Client Name")
            c1, c2 = st.columns(2)
            new_go = c1.checkbox("Generator Owner (GO)")
            new_gop = c2.checkbox("Generator Operator (GOP)")
            if st.form_submit_button("Create Asset"):
                if new_client_name:
                    execute_command("INSERT INTO clients (client_name, go_flag, gop_flag) VALUES (?, ?, ?)", (new_client_name, int(new_go), int(new_gop)))
                    st.success(f"Registered {new_client_name}!"); st.rerun()
    
    st.divider()
    clients_df = run_query("SELECT client_id, client_name, go_flag, gop_flag FROM clients")
    
    cols = st.columns(4)
    for idx, row in clients_df.iterrows():
        with cols[idx % 4]:
            st.markdown(f"""
            <div class="monday-card" style="text-align: left; border-left: 5px solid #00a0dc; margin-bottom: 20px;">
                <h3 style="margin:0;">{row['client_name']}</h3>
                <p style="font-size: 14px; color: #000; margin-top: 5px; font-weight:bold;">
                   {'✅ GO' if row['go_flag'] else '⬜ GO'} | {'✅ GOP' if row['gop_flag'] else '⬜ GOP'}
                </p>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.subheader("Workspace Actions")
    
    c_list = clients_df['client_name'].tolist()
    if c_list:
        selected_client = st.selectbox("Select Client context", c_list)
        if selected_client:
            c_details = run_query("SELECT * FROM clients WHERE client_name = ?", params=(selected_client,)).iloc[0]
            c_id = int(c_details['client_id'])
            
            t1, t2, t3 = st.tabs(["⚙️ Settings", "⚡ Automations", "📋 Standard Roster"])
            
            with t1:
                with st.form("client_config"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("#### Functional Roles")
                        is_go = st.checkbox("Generator Owner (GO)", value=bool(c_details['go_flag']))
                        is_gop = st.checkbox("Generator Operator (GOP)", value=bool(c_details['gop_flag']))
                    with c2:
                        st.markdown("#### Regional Entity")
                        current_region = c_details['regional_entity'] if c_details['regional_entity'] else "Texas RE"
                        options = ["Texas RE", "WECC", "SERC", "NPCC", "MRO", "RF"]
                        try: idx = options.index(current_region)
                        except: idx = 0
                        region = st.selectbox("Region", options, index=idx)
                    st.markdown("---")
                    if st.form_submit_button("💾 Save Configuration"):
                        execute_command("UPDATE clients SET go_flag=?, gop_flag=?, regional_entity=? WHERE client_id=?", (int(is_go), int(is_gop), region, c_id))
                        st.success(f"Updated configuration for {selected_client}"); st.rerun()
                
                # --- THE DANGER ZONE (PURGE BUTTON) ---
                st.markdown("---")
                st.markdown("#### Danger Zone")
                st.caption("Use this to delete all tasks associated with this client to start over. This cannot be undone.")
                if st.button(f"⚠️ Purge All Tasks for {selected_client}", type="primary", use_container_width=True):
                    execute_command("DELETE FROM tasks WHERE client_id = ?", (c_id,))
                    st.success("All tasks purged successfully."); st.rerun()
                
            with t2:
                col1, col2 = st.columns(2)
                with col1:
                    st.info("Sync 10-Year Plan")
                    if st.button("⚡ Run Engine"):
                        with st.spinner("Processing..."):
                            count = automation.generate_tasks_for_client(c_id)
                            # AUTO-FIX: Set internal deadlines for newly generated tasks
                            execute_command("UPDATE tasks SET internal_due_date = date(due_date, '-30 days') WHERE internal_due_date IS NULL AND client_id=?", (c_id,))
                            if count > 0: st.balloons(); st.success(f"Generated {count} items")
                            else: st.warning("0 items generated. Ensure GO/GOP is checked in Settings!")
                with col2:
                    st.info("Export Report")
                    if st.button("📊 Download Excel"):
                        excel, name = reports.generate_legacy_style_excel(c_id)
                        if excel: st.download_button("Download .xlsx", excel, name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        else: st.error("No tasks found to export.")

            with t3:
                st.write(f"**Manage Enforced Standards for {selected_client}**")
                roster_df = run_query("""
                    SELECT standard_code, MAX(active_flag) as is_active, COUNT(task_id) as total_tasks, MIN(due_date) as next_deadline 
                    FROM tasks WHERE client_id = ? AND standard_code IS NOT NULL AND standard_code != ''
                    GROUP BY standard_code ORDER BY standard_code ASC
                """, params=(c_id,))
                
                if not roster_df.empty:
                    roster_df['is_active'] = roster_df['is_active'].astype(bool)
                    roster_df['next_deadline'] = pd.to_datetime(roster_df['next_deadline'], errors='coerce')
                    
                    edited_roster = st.data_editor(
                        roster_df,
                        key=f"roster_{c_id}",
                        disabled=["standard_code", "total_tasks", "next_deadline"],
                        column_config={
                            "is_active": st.column_config.CheckboxColumn("Enforce Standard", default=True),
                            "standard_code": st.column_config.TextColumn("Standard Code"),
                            "total_tasks": st.column_config.NumberColumn("Generated Tasks"),
                            "next_deadline": st.column_config.DateColumn("Next Deadline", format="MMM DD, YYYY")
                        },
                        use_container_width=True, hide_index=True
                    )
                    
                    if st.button("💾 Apply Master Standard Changes"):
                        conn = get_connection()
                        c = conn.cursor()
                        for _, row in edited_roster.iterrows():
                            is_active = 1 if row['is_active'] else 0
                            c.execute("UPDATE tasks SET active_flag = ? WHERE client_id = ? AND standard_code = ?", (is_active, c_id, row['standard_code']))
                        conn.commit(); conn.close()
                        st.success("Standards updated!"); st.rerun()
                else:
                    st.info("No standards generated yet.")

# --- LIBRARY ---
elif page == "Standards Library":
    st.title("Knowledge Base")
    st.dataframe(run_query("SELECT standard_code, sub_section, requirement_text FROM standards LIMIT 100"), use_container_width=True, hide_index=True)