# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# NERC Compliance OS

## Project Overview
Internal compliance management tool for EPE Consulting. Tracks NERC regulatory obligations, generates task schedules across a 10-year horizon, and manages compliance workflows for generation assets (GO/GOP).

## Tech Stack
- Frontend: Streamlit (Python)
- Database: SQLite (migrating to PostgreSQL)
- Auth: None yet (implementing Microsoft Entra ID)
- Notifications: None yet (implementing Outlook via Microsoft Graph API)
- Hosting: GitHub Codespaces (moving to Azure App Service)

## Architecture
- app.py: Main UI (543 lines, needs decomposition into Streamlit multi-page app)
- database.py: SQLite connection and schema init
- automation.py: Task generation engine with blueprint/template system
- parsers.py: Excel/CSV ingestion for standards and client data
- recurrence.py: Deadline scheduling rules (hardcoded, moving to DB-driven)
- reports.py: Excel export via xlsxwriter
- seed_standards.py: Master spreadsheet importer

## Code Rules
- NEVER use f-strings in SQL queries. Always use parameterized queries with ? placeholders.
- Use specific exception types (except ValueError, except sqlite3.IntegrityError). Never use bare except.
- All destructive database operations (DELETE, DROP) must have confirmation logic.
- Pin dependency versions in requirements.txt.
- All new features need docstrings and inline comments for complex logic.

## Current Priorities (30-day production sprint)
1. Fix SQL injection on line 182 of app.py (search filter uses f-string)
2. Add Microsoft Entra ID (Azure AD) authentication via MSAL
3. Migrate SQLite to PostgreSQL with Alembic migrations
4. Implement Outlook email alerts via Microsoft Graph API
5. Split app.py into Streamlit multi-page app structure
6. Add audit trail table for all write operations
7. Add confirmation dialogs for destructive actions
