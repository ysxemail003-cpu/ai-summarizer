from typing import List
from .text_utils import split_sentences, detect_language, sentence_scores


def summarize(text: str, max_sentences: int = 3, strategy: str = "frequency") -> List[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    if strategy == "lead":
        return sentences[: max_sentences]
    # frequency-based ranking
    lang = detect_language(text)
    scored = sentence_scores(sentences, lang)
    # sort by score desc, but keep original order when equal; then select top k by index order
    top_idx = sorted(sorted(scored, key=lambda x: -x[1])[: max_sentences], key=lambda x: x[0])
    return [sentences[i] for i, _ in top_idx]

