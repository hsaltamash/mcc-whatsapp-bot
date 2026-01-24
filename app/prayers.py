import csv
from datetime import date, timedelta

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

    d = tomorrow if "tomorrow" in msg else today
    row = PRAYER_TIMES.get(d)
    if not row:
        return None

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
            day = "tomorrow" if d == tomorrow else "today"
            return f"{label} time {day} is {row[key]}."

    return None
