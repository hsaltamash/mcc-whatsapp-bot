import os
from openai import OpenAI
from app.lifespan import kb

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Tier-2 prompt: prefer KB context, but can answer MCC-only if context is missing.
SYSTEM_PROMPT_WITH_CONTEXT = """You are the MCC East Bay (Pleasanton, CA) Ramadan Assistant.

Rules:
- Prefer the provided CONTEXT when available.
- Use CONTEXT to answer accurately and concisely.
- If CONTEXT is missing/insufficient, you MAY answer ONLY if the answer is specifically about MCC East Bay
  (programs, facilities, typical events, general logistics).
- If the question requires exact dates/times/prices or any religious ruling and it is not in CONTEXT,
  say you do not have that information and direct the user to MCC official announcements/website or the imam.
- Do NOT provide fatwas or religious rulings. Advise asking the imam.
- Do NOT answer generic Islamic questions unrelated to MCC East Bay.
- Keep the reply short and practical for WhatsApp.
"""

# Tier-3 prompt: no KB context. MCC-only, high-level, no guessing.
SYSTEM_PROMPT_MCC_ONLY = """You are answering ONLY questions about MCC East Bay (Pleasanton, CA).

Allowed topics:
- MCC East Bay programs and activities (including Ramadan programming at a high level)
- MCC facilities, services, logistics, and how to find official info
- How to navigate MCC information (website/calendar/contact)

Hard constraints:
- If the user asks for exact times/dates/prices and you don't have them, say you don't have that info and
  tell them to check MCC’s official schedule/website.
- Do NOT give religious rulings (fatwas). Direct to the imam.
- Do NOT answer generic Islamic questions not specific to MCC East Bay.
- If the question isn't clearly about MCC East Bay, say you can only answer MCC East Bay questions.
- Keep it concise for WhatsApp.
"""

FALLBACK_NO_CONTEXT = (
    "I don’t have that information in my notes. Please check MCC’s official website/events calendar "
    "or contact MCC. For religious rulings, please ask the imam."
)


def _is_time_or_price_or_date_question(q: str) -> bool:
    """
    Heuristic to avoid hallucinating exact values when no KB context exists.
    Expand keywords as needed.
    """
    s = q.lower()
    keywords = [
        "what time", "time is", "timing", "schedule", "starts at", "when is", "date", "tonight",
        "tomorrow", "today", "pm", "am",
        "price", "cost", "fee", "$", "how much",
    ]
    return any(k in s for k in keywords)


def answer_with_ai_or_fallback(question: str) -> str:
    """
    Tiered approach:
    - If KB context exists: answer using context (preferred) + allow MCC-only fill if needed.
    - If no KB context: allow MCC-only high-level answers ONLY (no exact times/dates/prices, no rulings).
    - If no API key: still works in demo mode using KB context; otherwise returns a safe fallback.
    """
    question = (question or "").strip()
    context = kb.retrieve_context_keyword(question)

    # No OpenAI key: run in deterministic demo mode.
    if not client:
        if context:
            return f"(Demo mode)\nBased on MCC notes:\n{context[:600]}"
        return FALLBACK_NO_CONTEXT

    # If we have context, use it (preferred) with MCC-only constraints.
    if context:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_WITH_CONTEXT},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
            ],
        )
        return resp.choices[0].message.content.strip()

    # No context: MCC-only answers (guardrails). Avoid exact values.
    if _is_time_or_price_or_date_question(question):
        return FALLBACK_NO_CONTEXT

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_MCC_ONLY},
            {"role": "user", "content": question},
        ],
    )
    return resp.choices[0].message.content.strip()
