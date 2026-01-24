"""
app.py — MCC WhatsApp Bot (Hackathon-friendly)

Features:
- Twilio WhatsApp webhook: POST /whatsapp
- Health endpoint: GET /
- Debug endpoint: GET /debug
- Keyword-based FAQ retrieval from kb/*.md (fast, reliable)
- Exact prayer time lookups from kb/prayer_times.csv (deterministic, immediate)
- Optional OpenAI response (grounded in retrieved context); gracefully falls back if API not set or fails

Required packages (requirements.txt):
- fastapi
- uvicorn
- python-multipart
- twilio
- openai
"""

from __future__ import annotations

import csv
import glob
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple, List

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from twilio.twiml.messaging_response import MessagingResponse

# OpenAI is optional for demo; the bot still works without it
try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


# -----------------------------
# Globals / Config
# -----------------------------
LAST_ERROR: str = ""
KB_TEXT: str = ""
KB_FILES_LOADED: List[str] = []

PRAYER_TIMES: Dict[str, Dict[str, str]] = {}  # key: YYYY-MM-DD -> row dict (lowercase keys)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None

SYSTEM_PROMPT = (
    "You are MCC East Bay Ramadan Assistant (Demo).\n"
    "Rules:\n"
    "- Answer ONLY using the provided CONTEXT.\n"
    "- If the answer is not in the context, say you don't have that information.\n"
    "- Do NOT give fatwas or religious rulings. Advise asking the imam.\n"
    "- Be concise and practical for WhatsApp.\n"
)

FALLBACK = (
    "I don’t have that info in my MCC notes yet. "
    "Please check MCC’s official website/schedule or contact the office. "
    "For religious rulings, please ask the imam."
)

# Keep replies short to avoid WhatsApp/Twilio length issues
MAX_REPLY_CHARS = 1200


# -----------------------------
# KB loading (Markdown)
# -----------------------------
def load_kb_text(kb_glob: str = "kb/*.md") -> None:
    """
    Loads all markdown files under kb/ into a single string for keyword-based retrieval.
    """
    global KB_TEXT, KB_FILES_LOADED
    parts: List[str] = []
    files = sorted(glob.glob(kb_glob))
    KB_FILES_LOADED = files[:]
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            parts.append(f.read())
    KB_TEXT = "\n\n".join(parts).strip()


def retrieve_context_keyword(q: str, max_chars: int = 2200) -> str:
    """
    Naive but effective MVP retrieval:
    - Split KB into paragraphs
    - Score paragraphs by query term frequency
    - Return top N paragraphs as context
    """
    if not KB_TEXT:
        return ""

    q_terms = [t for t in q.lower().replace("?", " ").replace(",", " ").split() if len(t) > 2]
    paras = [p.strip() for p in KB_TEXT.split("\n\n") if p.strip()]

    scored: List[Tuple[int, str]] = []
    for p in paras:
        pl = p.lower()
        score = sum(pl.count(t) for t in q_terms)
        if score > 0:
            scored.append((score, p))

    scored.sort(reverse=True, key=lambda x: x[0])
    top = [p for _, p in scored[:6]]
    ctx = "\n\n---\n\n".join(top).strip()
    return ctx[:max_chars]


# -----------------------------
# Prayer times loading (CSV)
# -----------------------------
def load_prayer_times_csv(path: str = "kb/prayer_times.csv") -> None:
    """
    CSV columns recommended (lowercase headers are fine):
    date,fajr,dhuhr,asr,maghrib,isha,taraweeh

    date format: YYYY-MM-DD
    time format: e.g. "7:28 PM"
    """
    global PRAYER_TIMES
    PRAYER_TIMES = {}

    if not os.path.exists(path):
        return

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = (row.get("date") or "").strip()
            if not d:
                continue
            # normalize keys to lowercase
            norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            PRAYER_TIMES[d] = norm


def _extract_date_iso(user_msg: str) -> str:
    """
    Minimal parser:
    - "today" -> today
    - "tomorrow" -> tomorrow
    - explicit "YYYY-MM-DD" -> that date
    Default -> today
    """
    msg = user_msg.lower()

    if "tomorrow" in msg:
        return (date.today() + timedelta(days=1)).isoformat()

    # detect YYYY-MM-DD anywhere
    for token in msg.replace(",", " ").split():
        if len(token) == 10 and token[4] == "-" and token[7] == "-":
            try:
                datetime.strptime(token, "%Y-%m-%d")
                return token
            except Exception:
                pass

    return date.today().isoformat()


def check_prayer_time_shortcuts(user_msg: str) -> Optional[str]:
    """
    If the message asks for an exact prayer time and we have the date row,
    return a deterministic answer; otherwise None.
    """
    msg = user_msg.lower()
    d = _extract_date_iso(msg)
    row = PRAYER_TIMES.get(d)
    if not row:
        return None

    # map common terms -> CSV key
    term_to_key = {
        "fajr": "fajr",
        "dhuhr": "dhuhr",
        "zuhr": "dhuhr",
        "zohar": "dhuhr",
        "asr": "asr",
        "maghrib": "maghrib",
        "iftar": "maghrib",
        "isha": "isha",
        "tarawih": "taraweeh",
        "taraweeh": "taraweeh",
    }

    matched: Optional[Tuple[str, str]] = None
    for term, key in term_to_key.items():
        if term in msg:
            matched = (term, key)
            break

    if not matched:
        return None

    term, key = matched
    t = (row.get(key) or "").strip()
    if not t:
        return None

    # label for user
    if term == "iftar":
        label = "Iftar (Maghrib)"
    elif key == "taraweeh":
        label = "Taraweeh"
    else:
        label = term.capitalize()

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    if d == today:
        day_label = "today"
    elif d == tomorrow:
        day_label = "tomorrow"
    else:
        day_label = d

    return f"{label} time {day_label} is {t}."


# -----------------------------
# AI Answering (optional)
# -----------------------------
def answer_with_ai_or_fallback(question: str) -> str:
    """
    Uses keyword retrieval to get context, then:
    - if OpenAI client available -> ask model to answer using ONLY context
    - else -> return a concise “based on notes” fallback
    """
    context = retrieve_context_keyword(question)

    if not context:
        return FALLBACK

    if not client:
        # Demo mode without API key: deterministic response from context
        return f"(Demo mode)\nBased on MCC notes:\n{context[:600]}"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
            ],
        )
        txt = (resp.choices[0].message.content or "").strip()
        return txt or FALLBACK
    except Exception as e:
        global LAST_ERROR
        LAST_ERROR = f"OpenAI error: {repr(e)}"
        return f"(AI temporarily unavailable)\nBased on MCC notes:\n{context[:600]}"


def clamp_reply(s: str) -> str:
    s = (s or "").strip()
    if len(s) <= MAX_REPLY_CHARS:
        return s
    return s[: MAX_REPLY_CHARS - 3].rstrip() + "..."


# -----------------------------
# FastAPI Lifespan (modern startup)
# -----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global LAST_ERROR
    try:
        load_kb_text()
        load_prayer_times_csv()
    except Exception as e:
        LAST_ERROR = f"Startup error: {repr(e)}"
    yield


app = FastAPI(lifespan=lifespan)


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/debug")
def debug():
    return JSONResponse(
        {
            "kb_loaded_chars": len(KB_TEXT),
            "kb_files_loaded": KB_FILES_LOADED,
            "prayer_dates_loaded": len(PRAYER_TIMES),
            "has_openai_key": bool(OPENAI_API_KEY),
            "last_error": LAST_ERROR,
        }
    )


@app.post("/whatsapp")
async def whatsapp(request: Request):
    """
    Twilio sends application/x-www-form-urlencoded with fields like:
    - Body
    - From
    - To
    """
    try:
        form = await request.form()
        user_msg = (form.get("Body") or "").strip()

        # 1) deterministic exact times (ALL prayers + taraweeh) if CSV exists
        reply = check_prayer_time_shortcuts(user_msg)

        # 2) otherwise answer from FAQ KB (+ optional AI, grounded)
        if not reply:
            reply = answer_with_ai_or_fallback(user_msg)

        reply = clamp_reply(reply)

    except Exception as e:
        # Never 500 back to Twilio; always respond with TwiML
        global LAST_ERROR
        LAST_ERROR = f"Webhook error: {repr(e)}"
        reply = "Sorry — the bot hit an error. Please try again."

    tw = MessagingResponse()
    tw.message(reply)
    return PlainTextResponse(str(tw), media_type="application/xml")
