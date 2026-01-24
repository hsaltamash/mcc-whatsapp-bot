import glob

KB_TEXT = ""
KB_FILES = []

def load_kb_text():
    global KB_TEXT, KB_FILES
    parts = []
    KB_FILES = sorted(glob.glob("kb/*.md"))
    for fp in KB_FILES:
        with open(fp, encoding="utf-8") as f:
            parts.append(f.read())
    KB_TEXT = "\n\n".join(parts)

def retrieve_context_keyword(q: str, max_chars=2200) -> str:
    if not KB_TEXT:
        return ""

    terms = [t for t in q.lower().split() if len(t) > 2]
    paras = [p for p in KB_TEXT.split("\n\n") if p.strip()]
    scored = []

    for p in paras:
        score = sum(p.lower().count(t) for t in terms)
        if score:
            scored.append((score, p))

    scored.sort(reverse=True)
    return "\n\n---\n\n".join(p for _, p in scored[:6])[:max_chars]
