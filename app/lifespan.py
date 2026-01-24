from contextlib import asynccontextmanager
from app.kb import load_kb_text
from app.prayers import load_prayer_times_csv

LAST_ERROR = ""

@asynccontextmanager
async def lifespan(app):
    global LAST_ERROR
    try:
        load_kb_text()
        load_prayer_times_csv()
    except Exception as e:
        LAST_ERROR = repr(e)
    yield
