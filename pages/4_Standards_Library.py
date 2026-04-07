"""Standards Library — NERC master list viewer and task blueprint manager."""
import json
import streamlit as st
import pandas as pd
from database import get_connection
from utils import apply_theme, ensure_db, run_query

st.set_page_config(page_title="Standards Library | NERC Manager", layout="wide")
apply_theme()
ensure_db()

st.title("Knowledge Base & Blueprints")

tab1, tab2 = st.tabs(["📚 NERC Master List", "📋 Task Templates Blueprint"])

# --- TAB 1: NERC MASTER LIST ---
with tab1:
    with st.expander("⚙️ Admin: Upload NERC Master Spreadsheet", expanded=False):
        st.warning("This will reset the Standards database and upload a new master list.")
        with st.form("seeder_form"):
            uploaded_file = st.file_uploader("Upload Master List", type=["xlsx", "xls", "csv"])
            submitted = st.form_submit_button("🚀 Process & Seed Database", type="primary")
            if submitted:
                if uploaded_file is None:
                    st.error("⚠️ Please browse and select a file before clicking Process.")
                else:
                    with st.spinner("Parsing spreadsheet... this may take a minute."):
                        try:
                            with open("master.xlsx", "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            import seed_standards
                            seed_standards.seed_database()
                            count_df = run_query("SELECT COUNT(*) as c FROM standards")
                            inserted_count = count_df.iloc[0]["c"]
                            if inserted_count > 0:
                                st.success(f"✅ Database successfully seeded with {inserted_count} requirements!")
                            else:
                                st.error("❌ The script ran, but 0 rows were added. Check your Excel column headers.")
                        except Exception as e:
                            st.error(f"Seeding failed: {e}")

    st.divider()
    try:
        df_standards = run_query(
            "SELECT standard_code, sub_section, requirement_text, applicability_tags FROM standards"
        )
        if df_standards.empty:
            st.info("The Standards Library is currently empty. Please upload the Master Spreadsheet above.")
        else:
            st.metric("Total Requirements Tracked", len(df_standards))
            st.dataframe(df_standards, use_container_width=True, hide_index=True)
    except Exception:
        st.warning("Standards table not initialized. Please upload the master spreadsheet to build the database.")

# --- TAB 2: TASK BLUEPRINTS ---
with tab2:
    st.write("### Master Task Blueprints")
    st.caption(
        "Define the specific subtasks that should be generated for each standard. "
        "'Days Offset' determines how many days before the NERC target date this specific step is due."
    )

    # --- BACKUP & RESTORE ---
    c_down, c_up, c_btn = st.columns([1, 1.5, 1])
    with c_down:
        try:
            current_blueprints = run_query(
                "SELECT standard_code, task_title, applicability_tags, days_offset FROM task_templates"
            )
            csv_data = current_blueprints.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Backup Blueprints (CSV)",
                data=csv_data,
                file_name="nerc_blueprints.csv",
                mime="text/csv",
                use_container_width=True,
            )
        except Exception:
            pass
    with c_up:
        restore_file = st.file_uploader("Restore", type=["csv"], label_visibility="collapsed")
    with c_btn:
        if restore_file and st.button("📤 Restore from CSV", use_container_width=True):
            df_restore = pd.read_csv(restore_file)
            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM task_templates")
            for _, r in df_restore.iterrows():
                c.execute(
                    "INSERT INTO task_templates (standard_code, task_title, applicability_tags, days_offset) VALUES (?, ?, ?, ?)",
                    (r["standard_code"], r["task_title"], str(r["applicability_tags"]), r["days_offset"]),
                )
            conn.commit()
            conn.close()
            st.success("Restored!")
            st.rerun()

    st.divider()

    # Fetch distinct standard codes for autocomplete
    try:
        std_df = run_query("SELECT DISTINCT standard_code FROM standards ORDER BY standard_code ASC")
        standard_options = std_df["standard_code"].tolist()
    except Exception:
        standard_options = []

    # --- ADD NEW BLUEPRINT ---
    with st.expander("➕ Add New Subtask Blueprint", expanded=False):
        with st.form("new_template_form"):
            c1, c2 = st.columns(2)
            t_code = c1.selectbox(
                "Standard Code", options=standard_options, index=None, placeholder="Type to search standards..."
            )
            t_title = c2.text_input("Subtask Title (e.g., Review Access Logs)")
            c3, c4 = st.columns(2)
            t_tags = c3.multiselect("Applies To", ["GO", "GOP", "BA", "TO", "TOP"], default=["GO", "GOP"])
            t_offset = c4.number_input("Days Before Regulatory Target", min_value=0, max_value=365, value=30)

            if st.form_submit_button("Add to Blueprint"):
                if t_code and t_title:
                    conn = get_connection()
                    conn.execute(
                        "INSERT INTO task_templates (standard_code, task_title, applicability_tags, days_offset) VALUES (?, ?, ?, ?)",
                        (t_code.strip().upper(), t_title.strip(), json.dumps(t_tags), int(t_offset)),
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"Added '{t_title}' to {t_code.upper()}!")
                    st.rerun()
                else:
                    st.error("⚠️ Standard Code and Subtask Title are required.")

    st.divider()

    # --- DISPLAY & EDIT BLUEPRINTS ---
    try:
        templates_df = run_query(
            "SELECT * FROM task_templates ORDER BY standard_code ASC, days_offset DESC"
        )
        if not templates_df.empty:
            edited_templates = st.data_editor(
                templates_df,
                key="template_editor",
                num_rows="dynamic",
                disabled=["template_id"],
                column_config={
                    "standard_code": st.column_config.SelectboxColumn("Standard Code", options=standard_options, required=True),
                    "task_title": st.column_config.TextColumn("Subtask Name", width="large", required=True),
                    "applicability_tags": st.column_config.TextColumn("Tags (JSON)", required=True),
                    "days_offset": st.column_config.NumberColumn("Days Offset", required=True),
                },
                use_container_width=True,
                hide_index=False,
            )

            if st.button("💾 Save Template Changes", type="primary"):
                conn = get_connection()
                c = conn.cursor()

                original_ids = set(templates_df["template_id"].dropna())
                remaining_ids = set(edited_templates["template_id"].dropna())
                deleted_ids = original_ids - remaining_ids

                for tid in deleted_ids:
                    c.execute("DELETE FROM task_templates WHERE template_id = ?", (int(tid),))

                for _, row in edited_templates.dropna(subset=["template_id"]).iterrows():
                    c.execute(
                        "UPDATE task_templates SET standard_code=?, task_title=?, applicability_tags=?, days_offset=? WHERE template_id=?",
                        (row["standard_code"], row["task_title"], str(row["applicability_tags"]), row["days_offset"], row["template_id"]),
                    )
                conn.commit()
                conn.close()
                st.success(f"Blueprints updated! ({len(deleted_ids)} deleted).")
                st.rerun()
        else:
            st.info("No subtask blueprints defined yet. Add one above to start building your library!")
    except Exception:
        pass
