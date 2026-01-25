from contextlib import asynccontextmanager
from app.kb import KnowledgeBase
from app.prayers import load_prayer_times_csv

# Global instance for the knowledge base
kb = KnowledgeBase()
LAST_ERROR = ""

@asynccontextmanager
async def lifespan(app):
    global LAST_ERROR
    try:
        kb.load_kb_text()
        load_prayer_times_csv()
    except Exception as e:
        LAST_ERROR = repr(e)
    yield