"""NERC Compliance OS — main entry point.

Initializes the database and redirects to the Dashboard page.
All UI logic lives in pages/.
https://nerc-beta-test.streamlit.app/
"""
import streamlit as st
from utils import apply_theme, ensure_db

st.set_page_config(page_title="NERC Manager", layout="wide")
apply_theme()
ensure_db()

st.switch_page("pages/1_Dashboard.py")
