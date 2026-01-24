from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from app.prayers import check_prayer_time_shortcuts
from app.ai import answer_with_ai_or_fallback
from app.utils import clamp_reply

router = APIRouter()

@router.post("/whatsapp")
async def whatsapp(request: Request):
    try:
        form = await request.form()
        user_msg = (form.get("Body") or "").strip()

        reply = check_prayer_time_shortcuts(user_msg)
        if not reply:
            reply = answer_with_ai_or_fallback(user_msg)

        reply = clamp_reply(reply)

    except Exception:
        reply = "Sorry — the bot hit an error. Please try again."

    tw = MessagingResponse()
    tw.message(reply)
    return PlainTextResponse(str(tw), media_type="application/xml")
