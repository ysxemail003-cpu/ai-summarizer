from typing import Optional
from .text_utils import split_sentences, detect_language


FILLER_EN = {"basically","actually","just","really","very","kind","sort","literally"}
FORMAL_REPL = {
    # informal -> formal
    "gonna": "going to",
    "wanna": "want to",
    "gotta": "have to",
    "ok": "okay",
}


def optimize(text: str, style: str = "concise", language: Optional[str] = None) -> str:
    lang = language or detect_language(text)
    sents = split_sentences(text)
    if not sents:
        return ""

    if style == "bullet":
        items = [f"- {s}" for s in sents]
        return "\n".join(items)

    if style == "formal":
        out = text
        for k, v in FORMAL_REPL.items():
            out = out.replace(k, v).replace(k.capitalize(), v.capitalize())
        return out

    # concise: remove fillers, compress whitespace
    if lang == "en":
        words = text.split()
        words = [w for w in words if w.lower() not in FILLER_EN]
        out = " ".join(words)
    else:
        out = text
    out = " ".join(out.split())
    return out

