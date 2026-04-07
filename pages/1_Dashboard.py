"""Executive Dashboard — at-a-glance KPIs and critical deadline board."""
import streamlit as st
from datetime import datetime, timedelta
from utils import apply_theme, ensure_db, run_query

st.set_page_config(page_title="Dashboard | NERC Manager", layout="wide")
apply_theme()
ensure_db()

st.title("Executive Dashboard")
st.markdown("Welcome to the NERC Compliance Tester. Please review the tabs on the left to navigate assets and tasks.")
st.divider()

next_90 = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

try:
    task_counts = run_query("SELECT status, COUNT(*) as count FROM tasks WHERE active_flag=1 GROUP BY status")
    total = task_counts["count"].sum() if not task_counts.empty else 0
    pending = task_counts[task_counts["status"] == "Pending"]["count"].sum() if not task_counts.empty else 0

    upcoming = run_query(
        "SELECT COUNT(*) as count FROM tasks WHERE internal_due_date <= ? AND status != 'Completed' AND active_flag=1",
        (next_90,),
    ).iloc[0]["count"]
    client_count = run_query("SELECT COUNT(*) as count FROM clients WHERE active_flag=1").iloc[0]["count"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="monday-card" style="border-left-color: #00c875;"><h3>Active Tasks</h3><h2>{total}</h2></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="monday-card" style="border-left-color: #fdab3d;"><h3>Pending Actions</h3><h2>{pending}</h2></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="monday-card" style="border-left-color: #ff5ac8;"><h3>Due Next 90 Days</h3><h2>{upcoming}</h2></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="monday-card" style="border-left-color: #579bfc;"><h3>Active Clients</h3><h2>{client_count}</h2></div>', unsafe_allow_html=True)
except Exception as e:
    st.error(f"Data Error: {e}")

st.subheader("⚠️ Critical Attention Board")
critical_df = run_query(
    """
    SELECT t.task_id, c.client_name, t.title, t.internal_due_date, t.due_date, t.priority, t.status
    FROM tasks t
    JOIN clients c ON t.client_id = c.client_id
    WHERE t.status != 'Completed' AND t.internal_due_date <= ? AND t.active_flag=1
    ORDER BY t.internal_due_date ASC
    LIMIT 10
    """,
    (next_90,),
)
if not critical_df.empty:
    st.dataframe(
        critical_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "status": st.column_config.TextColumn("Status"),
            "internal_due_date": st.column_config.DateColumn("Internal Target", format="MMM DD, YYYY"),
            "due_date": st.column_config.DateColumn("Regulatory Deadline", format="MMM DD, YYYY"),
            "title": st.column_config.TextColumn("Task Name", width="large"),
            "priority": st.column_config.TextColumn("Urgency"),
        },
    )
else:
    st.success("All caught up! No critical deadlines.")
