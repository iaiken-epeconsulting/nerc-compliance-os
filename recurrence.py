from datetime import datetime, timedelta

def get_recurrence_rule(standard_code):
    """
    Returns the recurrence rule for a given Standard Code.
    Returns: (frequency_type, interval_value, specific_month, specific_day)
    """
    code = standard_code.upper()
    
    # --- CYBER SECURITY (CIP) ---
    if "CIP-002" in code: return ("annual", 1, 4, 1) # Review Assets (April)
    if "CIP-003" in code: return ("annual", 1, 4, 1) # Policy Review
    if "CIP-014" in code: return ("periodic", 3, 1, 15) # Physical Security (Every 3 years)

    # --- PROTECTION (PRC) ---
    if "PRC-005" in code: return ("annual", 1, 1, 1) # Maintenance Plans (Placeholder)
    if "PRC-019" in code: return ("periodic", 5, 1, 1) # Coordination (5 Years)
    if "PRC-023" in code: return ("annual", 1, 1, 1) # Relay Loadability
    if "PRC-024" in code: return ("event", 0, 1, 1) # Event driven

    # --- MODELING (MOD) ---
    if "MOD-025" in code: return ("periodic", 5, 7, 1) # Reactive Power (5 Years)
    if "MOD-026" in code: return ("periodic", 10, 7, 1) # Excitation (10 Years)
    if "MOD-027" in code: return ("periodic", 10, 7, 1) # Frequency (10 Years)
    if "MOD-032" in code: return ("annual", 1, 7, 1) # Model Data (July)

    # --- EMERGENCY (EOP) ---
    if "EOP-011" in code: return ("annual", 1, 10, 1) # Cold Weather Prep
    if "EOP-012" in code: return ("annual", 1, 10, 1) # Extreme Cold

    # --- COMMUNICATIONS (COM) ---
    if "COM-001" in code: return ("annual", 1, 12, 1)
    if "COM-002" in code: return ("annual", 1, 12, 1)

    # DEFAULT
    return ("annual", 1, 4, 1)

def generate_dates(start_year, years_to_project, rule):
    """
    Generates a list of date objects based on the rule.
    """
    freq_type, interval, month, day = rule
    dates = []
    
    if freq_type == 'event':
        # Even for event-driven, we schedule an annual "Review Procedure" check
        for i in range(years_to_project):
            dates.append(datetime(start_year + i, 1, 15).date())
            
    elif freq_type == 'annual':
        for i in range(years_to_project):
            try:
                d = datetime(start_year + i, month, day).date()
                dates.append(d)
            except ValueError:
                dates.append(datetime(start_year + i, month, 28).date())

    elif freq_type == 'periodic':
        # Start from current year, add interval
        current = start_year
        while current < start_year + years_to_project:
            try:
                d = datetime(current, month, day).date()
                dates.append(d)
            except ValueError:
                dates.append(datetime(current, month, 28).date())
            current += interval

    elif freq_type == 'quarterly':
        for i in range(years_to_project):
            year = start_year + i
            dates.append(datetime(year, 3, 31).date())
            dates.append(datetime(year, 6, 30).date())
            dates.append(datetime(year, 9, 30).date())
            dates.append(datetime(year, 12, 31).date())

    return dates