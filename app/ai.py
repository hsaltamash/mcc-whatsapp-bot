import os
from openai import OpenAI
from app.kb import retrieve_context_keyword

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

def answer_with_ai_or_fallback(question: str) -> str:
    context = retrieve_context_keyword(question)
    if not context:
        return "I don’t have that information yet. Please check MCC’s website."

    if not client:
        return f"(Demo mode)\nBased on MCC notes:\n{context[:600]}"

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": "Answer only from context."},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
        ],
    )
    return resp.choices[0].message.content.strip()
