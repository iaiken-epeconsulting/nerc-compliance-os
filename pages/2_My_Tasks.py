"""My Tasks — compliance task board with filtering, inline editing, and deletion."""
import streamlit as st
import pandas as pd
from datetime import timedelta
from database import get_connection
from utils import apply_theme, ensure_db, run_query, execute_command, USER_LIST, FREQ_LIST

st.set_page_config(page_title="My Tasks | NERC Manager", layout="wide")
apply_theme()
ensure_db()

st.title("Board: Compliance Tasks")
st.caption("💡 To delete a task, click the gray box on the far left of the row, click the trash can, and hit 'Save Changes'.")

# --- TASK CREATION FORM ---
with st.expander("➕ New Custom Task"):
    with st.form("quick_add"):
        st.write("Add Ad-Hoc Task")
        client_list = run_query("SELECT client_name FROM clients")["client_name"].tolist()
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
                    cid = run_query(
                        "SELECT client_id FROM clients WHERE client_name=?", (qa_client,)
                    ).iloc[0]["client_id"]
                    internal_target = qa_date - timedelta(days=30)
                    execute_command(
                        "INSERT INTO tasks (client_id, title, due_date, internal_due_date, priority, assigned_to, frequency, status, source, active_flag) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Manual', 1)",
                        (int(cid), qa_title, qa_date, internal_target, qa_priority, qa_assignee, qa_freq),
                    )
                    st.success("Added! Internal deadline auto-set to 30 days prior.")
                    st.rerun()
        else:
            st.warning("Create a client first!")

st.divider()

# --- FILTERS ---
f1, f2, f3, f4 = st.columns(4)
with f1:
    client_opts = ["All"] + run_query("SELECT client_name FROM clients")["client_name"].tolist()
    filter_asset = st.selectbox("Filter Asset", client_opts)
with f2:
    filter_user = st.selectbox("Assignee", ["All"] + USER_LIST)
with f3:
    filter_status = st.selectbox("Status", ["All", "Pending", "In Progress", "Completed"])
with f4:
    search = st.text_input("Search", placeholder="Type to search...")

# --- BUILD QUERY WITH PARAMETERIZED FILTERS ---
# NOTE: Filters are applied with ? placeholders — no f-strings in SQL per code rules.
base_query = """
    SELECT t.task_id, c.client_name, t.title, t.description, t.internal_due_date, t.due_date,
           t.frequency, t.priority, t.assigned_to, t.status
    FROM tasks t
    JOIN clients c ON t.client_id = c.client_id
    WHERE t.active_flag = 1
"""
params = []
if filter_asset != "All":
    base_query += " AND c.client_name = ?"
    params.append(filter_asset)
if filter_status != "All":
    base_query += " AND t.status = ?"
    params.append(filter_status)
if filter_user != "All":
    base_query += " AND t.assigned_to = ?"
    params.append(filter_user)
if search:
    # Use LIKE with a parameterized value — the % wildcards are in the value, not the query string.
    base_query += " AND t.title LIKE ?"
    params.append(f"%{search}%")

df = run_query(base_query + " ORDER BY t.internal_due_date ASC", params if params else None)

if df.empty:
    st.info("No tasks found matching your filters.")
else:
    df["priority"] = df["priority"].fillna("🟡 Medium")
    df["assigned_to"] = df["assigned_to"].fillna("Unassigned")
    df["frequency"] = df["frequency"].fillna("Annual")
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["internal_due_date"] = pd.to_datetime(df["internal_due_date"], errors="coerce")

    edited_df = st.data_editor(
        df,
        key="task_editor",
        disabled=["task_id", "client_name"],
        num_rows="dynamic",  # enables row deletion via the trash icon
        column_config={
            "title": st.column_config.TextColumn("Task Name", width="large", required=True),
            "client_name": st.column_config.TextColumn("Asset", width="medium"),
            "description": st.column_config.TextColumn("Notes", width="small"),
            "internal_due_date": st.column_config.DateColumn("Internal Target", format="MMM DD, YYYY"),
            "due_date": st.column_config.DateColumn("Regulatory Deadline", format="MMM DD, YYYY"),
            "frequency": st.column_config.SelectboxColumn("Cycle", options=FREQ_LIST, width="small"),
            "priority": st.column_config.SelectboxColumn("Urgency", options=["🔴 High", "🟡 Medium", "🟢 Low"], width="small", required=True),
            "assigned_to": st.column_config.SelectboxColumn("Assignee", options=USER_LIST, width="small"),
            "status": st.column_config.SelectboxColumn("Status", options=["Pending", "In Progress", "Completed", "Deferred"], width="small", required=True),
        },
        use_container_width=True,
        hide_index=False,
    )

    if st.button("💾 Save Changes", type="primary"):
        conn = get_connection()
        c = conn.cursor()

        # Detect deletions: IDs in original set but missing from editor
        original_ids = set(df["task_id"].dropna())
        remaining_ids = set(edited_df["task_id"].dropna())
        deleted_ids = original_ids - remaining_ids

        for tid in deleted_ids:
            c.execute("DELETE FROM tasks WHERE task_id = ?", (int(tid),))

        # Persist edits to surviving rows
        for _, row in edited_df.dropna(subset=["task_id"]).iterrows():
            save_date = row["due_date"].date() if pd.notnull(row["due_date"]) else None
            internal_date = row["internal_due_date"].date() if pd.notnull(row["internal_due_date"]) else None
            c.execute(
                """UPDATE tasks
                   SET status=?, due_date=?, internal_due_date=?, description=?, title=?, priority=?, assigned_to=?, frequency=?
                   WHERE task_id=?""",
                (row["status"], save_date, internal_date, row["description"], row["title"], row["priority"], row["assigned_to"], row["frequency"], row["task_id"]),
            )

        conn.commit()
        conn.close()
        st.success(f"Board updated! ({len(deleted_ids)} deleted).")
        st.rerun()
