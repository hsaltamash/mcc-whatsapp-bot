import csv
from datetime import date, timedelta, datetime
import re

PRAYER_TIMES = {}

def load_prayer_times_csv(path="kb/daily_prayer_times.csv"):
    global PRAYER_TIMES
    PRAYER_TIMES = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            PRAYER_TIMES[row["date"]] = {k.lower(): v for k, v in row.items()}

def check_prayer_time_shortcuts(msg: str):
    msg = msg.lower()
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Parse date from message (e.g., "27-03", "03-27", "27th March", "27 Mar", "27th March 2026", or just "27")
    parsed_date = None
    # First, check for hyphenated dates (DD-MM or MM-DD)
    hyphen_match = re.search(r'(\d{1,2})-(\d{1,2})(?:-(\d{4}))?', msg)
    if hyphen_match:
        a, b, year = hyphen_match.groups()
        a, b = int(a), int(b)
        year = int(year) if year else 2026
        # Try DD-MM first if a > 12 (likely day), else MM-DD
        if a > 12 and b <= 12:
            day, month = a, b
        elif b > 12 and a <= 12:
            day, month = b, a
        else:
            # Ambiguous, try DD-MM then MM-DD
            try:
                datetime(year, b, a)  # DD-MM
                day, month = a, b
            except ValueError:
                try:
                    datetime(year, a, b)  # MM-DD
                    day, month = b, a
                except ValueError:
                    pass
        if 1 <= day <= 31 and 1 <= month <= 12:
            try:
                parsed_date = datetime(year, month, day).date().isoformat()
            except ValueError:
                pass

    # If no hyphenated date, try regex for month-based dates (e.g., "27th March", "March 27th")
    if not parsed_date:
        # Clean ordinals and find day-month patterns
        cleaned_msg = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', msg)
        # Look for number followed by word (potential month)
        day_month_match = re.search(r'(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?', cleaned_msg)
        if day_month_match:
            day_str, month_str, year_str = day_month_match.groups()
            day = int(day_str)
            year = int(year_str) if year_str else 2026
            try:
                # Try full month name
                month = datetime.strptime(month_str, "%B").month
                parsed_date = datetime(year, month, day).date().isoformat()
            except ValueError:
                try:
                    # Try abbreviated month name
                    month = datetime.strptime(month_str, "%b").month
                    parsed_date = datetime(year, month, day).date().isoformat()
                except ValueError:
                    pass
        # Also check for month followed by day (e.g., "March 27th")
        if not parsed_date:
            month_day_match = re.search(r'(\w+)\s+(\d{1,2})(?:\s+(\d{4}))?', cleaned_msg)
            if month_day_match:
                month_str, day_str, year_str = month_day_match.groups()
                day = int(day_str)
                year = int(year_str) if year_str else 2026
                try:
                    month = datetime.strptime(month_str, "%B").month
                    parsed_date = datetime(year, month, day).date().isoformat()
                except ValueError:
                    try:
                        month = datetime.strptime(month_str, "%b").month
                        parsed_date = datetime(year, month, day).date().isoformat()
                    except ValueError:
                        pass

    # If still no date, check for standalone day (e.g., "27")
    if not parsed_date:
        day_match = re.search(r'\b(\d{1,2})\b', msg)
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                current_month = date.today().month
                current_year = date.today().year
                try:
                    parsed_date = datetime(current_year, current_month, day).date().isoformat()
                except ValueError:
                    pass  # Invalid date for current month (e.g., Feb 30)

    d = parsed_date if parsed_date else (tomorrow if "tomorrow" in msg else today)
    row = PRAYER_TIMES.get(d)
    if not row:
        return f"No prayer times available for {d}."

    mapping = {
        "fajr": "fajr",
        "fajar": "fajr",
        "fajir": "fajr",
        "dhuhr": "dhuhr",
        "dhuhar": "dhuhr",
        "zuhar": "dhuhr",
        "zuhr": "dhuhr",
        "asr": "asr",
        "asar": "asr",
        "asr": "asr",
        "maghrib": "maghrib",
        "magrib": "maghrib",
        "maghrib": "maghrib",
        "iftar": "maghrib",
        "aftar": "maghrib",
        "iftari": "maghrib",
        "aftari": "maghrib",
        "isha": "isha",
        "isha'a": "isha",
        "ishaa": "isha",
        "ishah": "isha",
        "esha": "isha",
        "taraweeh": "taraweeh",
        "tarawih": "taraweeh",
    }

    for term, key in mapping.items():
        if term in msg and row.get(key):
            label = "Iftar (Maghrib)" if term == "iftar" else term.capitalize()
            day_desc = f"on {d}" if parsed_date else ("tomorrow" if d == tomorrow else "today")
            return f"{label} time {day_desc} is {row[key]}."

    return None