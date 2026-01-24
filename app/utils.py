MAX_REPLY_CHARS = 1200

def clamp_reply(text: str) -> str:
    return text if len(text) <= MAX_REPLY_CHARS else text[:MAX_REPLY_CHARS - 3] + "..."
