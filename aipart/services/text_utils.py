import re
from typing import List, Tuple, Dict, Optional
import os
import json

CJK_REGEX = re.compile(r"[\u4e00-\u9fff]")

# 用提取法同时支持中英文标点与无空格中文分句
SENT_EXTRACT_REGEX = re.compile(r"[^。！？.!?\n]+[。！？.!?]?")
TOKEN_REGEX = re.compile(r"[\w]+|[\u4e00-\u9fff]")

EN_STOP = {
    "a","an","the","and","or","but","if","in","on","at","to","of","for","with","is","are","was","were","be","been","being","as","by","it","this","that","these","those","from","we","you","they","i","he","she","them","his","her","their"
}

ZH_STOP = {"的","了","和","是","在","我","有","就","不","人","都","一","一个","上","也","很","到","说","要","去"}


def detect_language(text: str) -> str:
    return "zh" if CJK_REGEX.search(text or "") else "en"


def split_sentences(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in SENT_EXTRACT_REGEX.findall(text) if p and p.strip()]
    return parts


def tokenize(text: str, lang: str) -> List[str]:
    if not text:
        return []
    tokens = TOKEN_REGEX.findall(text.lower())
    if lang == "zh":
        stop = ZH_STOP
    else:
        stop = EN_STOP
    return [t for t in tokens if t not in stop]


def sentence_scores(sentences: List[str], lang: str) -> List[Tuple[int, float]]:
    # Build token frequency
    from collections import Counter
    tokens_all: List[str] = []
    per_sentence_tokens: List[List[str]] = []
    for s in sentences:
        toks = tokenize(s, lang)
        per_sentence_tokens.append(toks)
        tokens_all.extend(toks)
    freq = Counter(tokens_all)
    # Avoid division by zero
    if not tokens_all:
        return [(i, 0.0) for i, _ in enumerate(sentences)]
    max_f = max(freq.values())
    scores: List[Tuple[int, float]] = []
    for i, toks in enumerate(per_sentence_tokens):
        # normalized term frequency sum
        s = sum(freq[t] / max_f for t in toks)
        scores.append((i, s))
    return scores

# === 术语纠错（可选） ===
_CORR_LOADED = False
_CORR_ENABLE = False
_CORR_MAP: Dict[str, Dict[str, str]] = {"zh": {}, "en": {}}


def _str_to_bool(v: Optional[str], default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _parse_pairs(s: str) -> Dict[str, str]:
    # 支持 "错->对,foo->bar" 或 "错=>对,foo=>bar"
    out: Dict[str, str] = {}
    for raw in s.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if "=>" in raw:
            k, v = raw.split("=>", 1)
        elif "->" in raw:
            k, v = raw.split("->", 1)
        else:
            continue
        k, v = k.strip(), v.strip()
        if k:
            out[k] = v
    return out


def _load_corrections_once():
    global _CORR_LOADED, _CORR_ENABLE, _CORR_MAP
    if _CORR_LOADED:
        return
    _CORR_ENABLE = _str_to_bool(os.environ.get("TEXT_CORRECT_ENABLE"), False)
    def parse_map(env_json: str, env_pairs: str) -> Dict[str, str]:
        js = os.environ.get(env_json)
        if js:
            try:
                m = json.loads(js)
                return {str(k): str(v) for k, v in m.items()}
            except Exception:
                pass
        pairs = os.environ.get(env_pairs)
        if pairs:
            try:
                return _parse_pairs(pairs)
            except Exception:
                pass
        return {}
    _CORR_MAP = {
        "zh": parse_map("TEXT_CORRECT_MAP_ZH", "TEXT_CORRECT_PAIRS_ZH"),
        "en": parse_map("TEXT_CORRECT_MAP_EN", "TEXT_CORRECT_PAIRS_EN"),
    }
    _CORR_LOADED = True


def apply_corrections(text: str, lang: str) -> str:
    _load_corrections_once()
    if not _CORR_ENABLE or not text:
        return text
    mapping = _CORR_MAP.get(lang or "en") or {}
    if not mapping:
        return text
    out = text
    if lang == "en":
        # 英文按词边界替换
        for k, v in mapping.items():
            pattern = re.compile(rf"\b{re.escape(k)}\b")
            out = pattern.sub(v, out)
    else:
        # 中文直接子串替换
        for k, v in mapping.items():
            out = out.replace(k, v)
    return out
