"""ベンチマーク用の回答採点 (正規化 + 複数許容解)。"""
import re
import unicodedata


def normalize(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower().strip()
    s = re.sub(r"[\s\u3000,.;:!?\"'`「」『』()（）\[\]{}]+", "", s)
    return s


def extract_number(s):
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else None


def score_answer(pred, gold_answers, qtype="fact"):
    """Returns (correct: bool, method: str, detail: str)."""
    if not pred or not str(pred).strip():
        return False, "empty", ""
    pred_n = normalize(pred)
    golds = gold_answers if isinstance(gold_answers, list) else [gold_answers]
    for g in golds:
        g_n = normalize(str(g))
        if not g_n:
            continue
        if pred_n == g_n:
            return True, "exact", g
        if g_n in pred_n or pred_n in g_n:
            return True, "contains", g
    if qtype == "numeric":
        pn = extract_number(pred)
        for g in golds:
            gn = extract_number(str(g))
            if pn is not None and gn is not None and abs(pn - gn) < 1e-6:
                return True, "numeric", g
    return False, "miss", golds[0] if golds else ""
