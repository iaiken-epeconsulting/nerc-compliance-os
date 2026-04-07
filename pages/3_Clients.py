"""Client Registry — register assets, manage settings, run automations, and view standard rosters."""
import streamlit as st
import pandas as pd
from datetime import timedelta
from database import get_connection
import automation
import reports
from utils import apply_theme, ensure_db, run_query, execute_command

st.set_page_config(page_title="Clients | NERC Manager", layout="wide")
apply_theme()
ensure_db()

st.title("Client Registry")

# --- REGISTER NEW CLIENT ---
with st.expander("➕ Register New Asset / Client", expanded=False):
    with st.form("new_client_form"):
        st.write("Add a new Generation Asset or Client.")
        new_client_name = st.text_input("Client Name")
        c1, c2 = st.columns(2)
        new_go = c1.checkbox("Generator Owner (GO)")
        new_gop = c2.checkbox("Generator Operator (GOP)")
        if st.form_submit_button("Create Asset"):
            if new_client_name:
                execute_command(
                    "INSERT INTO clients (client_name, go_flag, gop_flag) VALUES (?, ?, ?)",
                    (new_client_name, int(new_go), int(new_gop)),
                )
                st.success(f"Registered {new_client_name}!")
                st.rerun()

st.divider()
clients_df = run_query("SELECT client_id, client_name, go_flag, gop_flag FROM clients")

# --- CLIENT CARDS GRID ---
cols = st.columns(4)
for idx, row in clients_df.iterrows():
    with cols[idx % 4]:
        st.markdown(
            f"""
            <div class="monday-card" style="text-align: left; border-left: 5px solid #00a0dc; margin-bottom: 20px;">
                <h3 style="margin:0;">{row['client_name']}</h3>
                <p style="font-size: 14px; color: #000; margin-top: 5px; font-weight:bold;">
                   {'✅ GO' if row['go_flag'] else '⬜ GO'} | {'✅ GOP' if row['gop_flag'] else '⬜ GOP'}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()
st.subheader("Workspace Actions")

c_list = clients_df["client_name"].tolist()
if not c_list:
    st.info("No clients registered yet. Add one above.")
    st.stop()

selected_client = st.selectbox("Select Client context", c_list)
if not selected_client:
    st.stop()

c_details = run_query("SELECT * FROM clients WHERE client_name = ?", params=(selected_client,)).iloc[0]
c_id = int(c_details["client_id"])

t1, t2, t3 = st.tabs(["⚙️ Settings", "⚡ Automations", "📋 Standard Roster"])

# --- SETTINGS TAB ---
with t1:
    with st.form("client_config"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Functional Roles")
            is_go = st.checkbox("Generator Owner (GO)", value=bool(c_details["go_flag"]))
            is_gop = st.checkbox("Generator Operator (GOP)", value=bool(c_details["gop_flag"]))
        with c2:
            st.markdown("#### Regional Entity")
            current_region = c_details["regional_entity"] if c_details["regional_entity"] else "Texas RE"
            options = ["Texas RE", "WECC", "SERC", "NPCC", "MRO", "RF"]
            try:
                idx = options.index(current_region)
            except ValueError:
                idx = 0
            region = st.selectbox("Region", options, index=idx)
        st.markdown("---")
        if st.form_submit_button("💾 Save Configuration"):
            execute_command(
                "UPDATE clients SET go_flag=?, gop_flag=?, regional_entity=? WHERE client_id=?",
                (int(is_go), int(is_gop), region, c_id),
            )
            st.success(f"Updated configuration for {selected_client}")
            st.rerun()

    # --- DANGER ZONE ---
    st.markdown("---")
    st.markdown("#### Danger Zone")
    st.caption("Use this to delete all tasks associated with this client to start over. This cannot be undone.")
    if st.button(f"⚠️ Purge All Tasks for {selected_client}", type="primary", use_container_width=True):
        execute_command("DELETE FROM tasks WHERE client_id = ?", (c_id,))
        st.success("All tasks purged successfully.")
        st.rerun()

# --- AUTOMATIONS TAB ---
with t2:
    col1, col2 = st.columns(2)
    with col1:
        st.info("Sync 10-Year Plan")
        if st.button("⚡ Run Engine"):
            with st.spinner("Processing..."):
                count = automation.generate_tasks_for_client(c_id)
                # Auto-set internal deadlines for tasks that were just generated
                execute_command(
                    "UPDATE tasks SET internal_due_date = date(due_date, '-30 days') WHERE internal_due_date IS NULL AND client_id=?",
                    (c_id,),
                )
                if count > 0:
                    st.balloons()
                    st.success(f"Generated {count} items")
                else:
                    st.warning("0 items generated. Ensure GO/GOP is checked in Settings!")
    with col2:
        st.info("Export Report")
        if st.button("📊 Download Excel"):
            excel, name = reports.generate_legacy_style_excel(c_id)
            if excel:
                st.download_button(
                    "Download .xlsx", excel, name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.error("No tasks found to export.")

    # --- BULK RESCHEDULE ---
    st.divider()
    st.markdown("#### 📅 Bulk Reschedule Deadlines")
    st.caption("Change the regulatory deadline for all 'Pending' tasks for this asset at the same time.")

    bc1, bc2 = st.columns([1, 1])
    new_bulk_date = bc1.date_input("New Target Deadline")
    if bc2.button("Apply to All Pending Tasks", type="primary", use_container_width=True):
        internal_bulk_date = new_bulk_date - timedelta(days=30)
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "UPDATE tasks SET due_date = ?, internal_due_date = ? WHERE client_id = ? AND status = 'Pending'",
            (new_bulk_date, internal_bulk_date, c_id),
        )
        conn.commit()
        conn.close()
        st.success(f"Successfully shifted all pending deadlines to {new_bulk_date.strftime('%B %d, %Y')}!")
        st.rerun()

# --- STANDARD ROSTER TAB ---
with t3:
    st.write(f"**Manage Enforced Standards for {selected_client}**")
    roster_df = run_query(
        """
        SELECT standard_code, MAX(active_flag) as is_active, COUNT(task_id) as total_tasks, MIN(due_date) as next_deadline
        FROM tasks WHERE client_id = ? AND standard_code IS NOT NULL AND standard_code != ''
        GROUP BY standard_code ORDER BY standard_code ASC
        """,
        params=(c_id,),
    )

    if not roster_df.empty:
        roster_df["is_active"] = roster_df["is_active"].astype(bool)
        roster_df["next_deadline"] = pd.to_datetime(roster_df["next_deadline"], errors="coerce")

        edited_roster = st.data_editor(
            roster_df,
            key=f"roster_{c_id}",
            disabled=["standard_code", "total_tasks", "next_deadline"],
            column_config={
                "is_active": st.column_config.CheckboxColumn("Enforce Standard", default=True),
                "standard_code": st.column_config.TextColumn("Standard Code"),
                "total_tasks": st.column_config.NumberColumn("Generated Tasks"),
                "next_deadline": st.column_config.DateColumn("Next Deadline", format="MMM DD, YYYY"),
            },
            use_container_width=True,
            hide_index=True,
        )

        if st.button("💾 Apply Master Standard Changes"):
            conn = get_connection()
            c = conn.cursor()
            for _, row in edited_roster.iterrows():
                is_active = 1 if row["is_active"] else 0
                c.execute(
                    "UPDATE tasks SET active_flag = ? WHERE client_id = ? AND standard_code = ?",
                    (is_active, c_id, row["standard_code"]),
                )
            conn.commit()
            conn.close()
            st.success("Standards updated!")
            st.rerun()
    else:
        st.info("No standards generated yet.")
