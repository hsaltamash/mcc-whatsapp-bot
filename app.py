from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
import os, glob, threading
from openai import OpenAI
from contextlib import asynccontextmanager

LAST_ERROR = ""
KB_TEXT = ""

def load_kb_text():
    global KB_TEXT
    parts = []
    for fp in glob.glob("kb/*.md"):
        parts.append(open(fp, encoding="utf-8").read())
    KB_TEXT = "\n\n".join(parts)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        load_kb_text()
    except Exception as e:
        global LAST_ERROR
        LAST_ERROR = f"Startup error: {repr(e)}"
    yield
    # Shutdown (nothing needed)


app = FastAPI(lifespan=lifespan)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

SYSTEM_PROMPT = (
    "You are MCC East Bay Ramadan Assistant (Demo).\n"
    "Rules:\n"
    "- Answer ONLY using the provided CONTEXT.\n"
    "- If the answer is not in the context, say you don't have that information.\n"
    "- Do NOT give fatwas. Advise asking the imam.\n"
    "- Keep replies short.\n"
)

FALLBACK = (
    "I don’t have that info in my MCC notes yet. "
    "Please check MCC’s official Ramadan schedule or contact the office. "
    "For religious rulings, please ask the imam."
)



@app.get("/")
def health():
    return {"status": "ok"}



def retrieve_context_keyword(q: str, max_chars: int = 2000) -> str:
    q_terms = [t for t in q.lower().split() if len(t) > 2]
    paras = [p.strip() for p in KB_TEXT.split("\n\n") if p.strip()]
    scored = []
    for p in paras:
        s = sum(p.lower().count(t) for t in q_terms)
        if s > 0:
            scored.append((s, p))
    scored.sort(reverse=True, key=lambda x: x[0])
    top = [p for _, p in scored[:5]]
    ctx = "\n\n---\n\n".join(top)
    return ctx[:max_chars]

def answer(question: str) -> str:
    global LAST_ERROR

    if not KB_TEXT:
        return "KB not loaded yet. Please try again."

    context = retrieve_context_keyword(question)
    if not context:
        return FALLBACK

    if not client:
        return f"(Demo mode - no AI key)\n\nBased on MCC notes:\n{context[:600]}"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"}
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        LAST_ERROR = f"OpenAI error: {repr(e)}"
        # graceful fallback: still answer from context
        return f"(AI temporarily unavailable)\n\nBased on MCC notes:\n{context[:600]}"



@app.get("/debug")
def debug():
    return {"kb_loaded_chars": len(KB_TEXT), "last_error": LAST_ERROR}


@app.post("/whatsapp")
async def whatsapp(request: Request):
    form = await request.form()
    user_msg = (form.get("Body") or "").strip()

    tw = MessagingResponse()
    tw.message(answer(user_msg))

    return PlainTextResponse(str(tw), media_type="application/xml")
