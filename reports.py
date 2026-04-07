import pandas as pd
import io
from datetime import datetime
from database import get_connection

def generate_legacy_style_excel(client_id):
    """
    Generates an Excel file that mimics the 'AstraWindCompliance.xlsx' format.
    - Uses V3 database columns (Internal Dates, Frequency, Assignee).
    - Excludes inactive standards (active_flag = 0).
    - Auto-generates Reference IDs (YYYY-MM-00X).
    """
    conn = get_connection()
    
    # 1. Fetch Client Name for filename
    try:
        client = pd.read_sql("SELECT client_name FROM clients WHERE client_id = ?", conn, params=(client_id,)).iloc[0]
        client_name = client['client_name']
    except:
        conn.close()
        return None, "Error.xlsx"
    
    # 2. Fetch Tasks (Sorted by Internal Target Date)
    query = """
        SELECT 
            standard_code, 
            title, 
            description, 
            internal_due_date,
            due_date, 
            frequency,
            assigned_to,
            status 
        FROM tasks 
        WHERE client_id = ? AND status != 'Completed' AND active_flag = 1
        ORDER BY internal_due_date ASC
    """
    df = pd.read_sql(query, conn, params=(client_id,))
    conn.close()

    # If no data, return None
    if df.empty:
        return None, f"{client_name}_Compliance_Tracker.xlsx"

    # Clean dates for processing
    df['internal_due_date'] = pd.to_datetime(df['internal_due_date'], errors='coerce')
    df['due_date'] = pd.to_datetime(df['due_date'], errors='coerce')

    # 3. Create Excel Buffer
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    sheet = workbook.add_worksheet("Compliance Tracking")
    
    # --- STYLES ---
    header_fmt = workbook.add_format({
        'bold': True, 'bg_color': '#D9E1F2', 'border': 1, 
        'text_wrap': True, 'valign': 'vcenter', 'align': 'center'
    })
    month_fmt = workbook.add_format({
        'bold': True, 'bg_color': '#B4C6E7', 'border': 1, 'font_size': 12
    })
    cell_fmt = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})
    date_fmt = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd', 'valign': 'top', 'align': 'center'})
    
    # --- SET COLUMN WIDTHS ---
    sheet.set_column(0, 0, 15)  # Ref
    sheet.set_column(1, 1, 45)  # Task Details
    sheet.set_column(2, 2, 25)  # Owner
    sheet.set_column(3, 3, 20)  # Personnel
    sheet.set_column(4, 5, 15)  # Dates
    sheet.set_column(6, 6, 15)  # Occurrence
    sheet.set_column(7, 7, 15)  # Status
    
    current_row = 0
    
    # 4. Group by Month and Write Data
    # Grouping by the Year-Month of the INTERNAL due date
    for period, group in df.groupby(df['internal_due_date'].dt.to_period('M')):
        if pd.isna(period):
            continue # Skip tasks with completely broken dates
            
        month_name = period.strftime('%B %Y')
        
        # A. Write Month Header
        sheet.merge_range(current_row, 0, current_row, 7, month_name, month_fmt)
        current_row += 1
        
        # B. Write Column Headers
        headers = ["Ref #", "Task Details", "Owner (Asset)", "Personnel", "Internal Target", "NERC Deadline", "Occurrence", "Status"]
        for col_num, col_name in enumerate(headers):
            sheet.write(current_row, col_num, col_name, header_fmt)
        current_row += 1
        
        # C. Write Tasks
        item_counter = 1
        for _, row in group.iterrows():
            # Generate Ref # (YYYY-MM-001)
            ref_num = f"{period.year}-{period.month:02d}-{item_counter:03d}"
            
            # Map DB fields
            task_details = f"{row['standard_code']} - {row['title']}"
            personnel = row['assigned_to'] if pd.notna(row['assigned_to']) else "Unassigned"
            freq = row['frequency'] if pd.notna(row['frequency']) else "Annual"
            
            # Write Row
            sheet.write(current_row, 0, ref_num, cell_fmt)
            sheet.write(current_row, 1, task_details, cell_fmt)
            sheet.write(current_row, 2, client_name, cell_fmt) 
            sheet.write(current_row, 3, personnel, cell_fmt)          
            
            # Handle Dates gracefully
            int_date = row['internal_due_date'].strftime('%Y-%m-%d') if pd.notna(row['internal_due_date']) else ""
            nerc_date = row['due_date'].strftime('%Y-%m-%d') if pd.notna(row['due_date']) else ""
            
            sheet.write(current_row, 4, int_date, date_fmt) 
            sheet.write(current_row, 5, nerc_date, date_fmt) 
            sheet.write(current_row, 6, freq, cell_fmt)    
            sheet.write(current_row, 7, row['status'], cell_fmt)
            
            current_row += 1
            item_counter += 1
            
        current_row += 1 # Blank row between months

    writer.close()
    output.seek(0)
    
    return output.getvalue(), f"{client_name}_Compliance_Tracker.xlsx"