"""Shared helpers, constants, and theme utilities for the NERC Compliance OS."""
import os
import streamlit as st
import pandas as pd
from database import init_db, get_connection

# --- CONSTANTS ---
USER_LIST = ["Unassigned", "Ian Aiken", "Jennifer Hart", "Calvin Wheatley", "Matthew Clairday"]
FREQ_LIST = ["Annual", "Quarterly", "Monthly", "Weekly", "Event-Driven", "One-Time"]

_CSS = """
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
    button[kind="primary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
    }
</style>
"""


def apply_theme():
    """Inject the shared CSS theme into the current page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def ensure_db():
    """Initialize the database once per session, creating the data directory if needed."""
    if not os.path.exists("data"):
        os.makedirs("data")
    if "db_setup" not in st.session_state:
        init_db()
        st.session_state["db_setup"] = True


def run_query(query, params=None):
    """Execute a SELECT query and return results as a DataFrame.

    Args:
        query: SQL query string with ? placeholders (never use f-strings).
        params: Optional tuple of parameter values.

    Returns:
        pandas DataFrame with query results.
    """
    conn = get_connection()
    try:
        return pd.read_sql(query, conn, params=params) if params else pd.read_sql(query, conn)
    finally:
        conn.close()


def execute_command(sql, params):
    """Execute a DML statement (INSERT/UPDATE/DELETE) with parameterized values.

    Args:
        sql: SQL statement with ? placeholders (never use f-strings).
        params: Tuple of parameter values.
    """
    conn = get_connection()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()
