from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
import os, glob

from openai import OpenAI
import chromadb
from chromaDdb.utils import embedding_functions

app = FastAPI()

# ---- CONFIG ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are MCC East Bay Ramadan Assistant (Demo).

Rules:
- Answer ONLY using the provided CONTEXT.
- If the answer is not in the context, say you don't have that information.
- Do NOT give fatwas or religious rulings. Advise asking the imam.
- Keep replies short and practical (WhatsApp-friendly).
"""

FALLBACK = (
    "I don’t have that info in my MCC notes yet. "
    "Please check MCC’s official Ramadan schedule or contact the office. "
    "For religious rulings, please ask the imam."
)

# ---- VECTOR DB ----
chroma = chromadb.Client()
embed_fn = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name="text-embedding-3-small"
)
kb = chroma.get_or_create_collection("mcc_kb", embedding_function=embed_fn)

def ingest_kb():
    kb.delete(where={})
    files = glob.glob("kb/*.md")
    i = 0
    for f in files:
        text = open(f, encoding="utf-8").read()
        chunks = [text[j:j+800] for j in range(0, len(text), 800)]
        for c in chunks:
            kb.add(documents=[c], ids=[f"{f}-{i}"])
            i += 1

ingest_kb()

def answer(question):
    res = kb.query(query_texts=[question], n_results=4)
    docs = res["documents"][0] if res["documents"] else []

    if not docs:
        return FALLBACK

    context = "\n\n".join(docs)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"}
        ],
    )

    return completion.choices[0].message.content.strip()

# ---- WHATSAPP WEBHOOK ----
@app.post("/whatsapp")
async def whatsapp(request: Request):
    form = await request.form()
    user_msg = form.get("Body", "").strip()

    response_text = answer(user_msg)

    tw = MessagingResponse()
    tw.message(response_text)

    return PlainTextResponse(str(tw), media_type="application/xml")
