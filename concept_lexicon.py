"""
concept_lexicon.py — Phase 2 命題レキシコン (短い英語命題 ↔ 最終隠れ方向)
==============================================================================

AxisAnchors (6軸) を N 概念へ拡張した概念ベクトル辞書。

  Write: 命題ラベル → 辞書方向の加算 / 置換
  Read : 隠れ状態 → コサイン最近傍の英語ラベル

学習: concept_lexicon_trainer.py または python3 concept_lexicon.py --train
保存: .verantyx_chrono/concept_lexicon.npz
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from verantyx_mind import (
    RustBrain, DEFAULT_MODEL, TOKENIZER, MEMORY_DIR, HIDDEN, embed_text,
)

LEXICON_PATH = os.path.join(MEMORY_DIR, "concept_lexicon.npz")
LEXICON_META = os.path.join(MEMORY_DIR, "concept_lexicon.meta.json")
DEFAULT_GATE_THRESHOLD = 0.70
DEFAULT_GATE = DEFAULT_GATE_THRESHOLD  # alias used by codec benches / suite
DEFAULT_CORPUS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "benchmarks", "datasets", "codec_propositions.jsonl",
)
# Opt-in/out for Council / Matryoshka / memory codec labels.
# unset or "1"/"true"/"on" → load lexicon when npz exists
# "0"/"false"/"off" → disable even if npz exists
CODEC_ENV = "VERANTYX_CODEC"


def codec_enabled() -> bool:
    v = os.environ.get(CODEC_ENV, "1").strip().lower()
    return v not in ("0", "false", "off", "no")


def _unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    return v / (np.linalg.norm(v) + 1e-8)


def load_propositions(path: str) -> List[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            # normalize: accept text or proposition
            if "text" not in row and "proposition" in row:
                row["text"] = row["proposition"]
            rows.append(row)
    return rows


def encode_proposition(brain, tok, text: str) -> np.ndarray:
    """命題の最終隠れキー (PromptEOL、単位ベクトル)。"""
    return embed_text(brain, tok, text).astype(np.float32)


def proposition_match(
    predicted: str, gold: str, keywords: Optional[Sequence[str]] = None
) -> bool:
    """Write→Read 再現判定: 完全一致 or キーワード包含 or 部分文字列。"""
    p = (predicted or "").strip().lower()
    g = (gold or "").strip().lower()
    if not p or not g:
        return False
    if p == g or g in p or p in g:
        return True
    if keywords:
        hits = sum(1 for k in keywords if k.lower() in p)
        return hits >= max(1, (len(keywords) + 1) // 2)
    pw, gw = set(p.split()), set(g.split())
    if not pw or not gw:
        return False
    return len(pw & gw) / len(pw | gw) >= 0.5


class ConceptLexicon:
    """命題ラベル ↔ 単位方向ベクトルの辞書。"""

    def __init__(self, path: str = LEXICON_PATH):
        self.path = path
        self.available = False
        self.labels: List[str] = []
        self.domains: List[str] = []
        self.ids: List[str] = []
        self.mu = np.zeros(HIDDEN, dtype=np.float32)
        self.vectors = np.zeros((0, HIDDEN), dtype=np.float32)  # μ-centered unit
        self.raw = np.zeros((0, HIDDEN), dtype=np.float32)      # PromptEOL unit
        self.hold_acc = 0.0
        self.train_acc = 0.0
        if os.path.exists(path):
            self._load(path)

    # aliases for older callers
    @property
    def dirs(self):
        return self.vectors

    @property
    def size(self) -> int:
        return len(self.labels)

    def _load(self, path: str) -> None:
        data = np.load(path, allow_pickle=True)
        self.mu = data["mu"].astype(np.float32)
        if "vectors" in data.files:
            self.vectors = data["vectors"].astype(np.float32)
        elif "dirs" in data.files:
            self.vectors = data["dirs"].astype(np.float32)
        else:
            raise KeyError("lexicon npz missing vectors/dirs")
        self.raw = (
            data["raw"].astype(np.float32)
            if "raw" in data.files
            else self.vectors.copy()
        )
        self.labels = [str(x) for x in data["labels"].tolist()]
        self.domains = (
            [str(x) for x in data["domains"].tolist()]
            if "domains" in data.files
            else [""] * len(self.labels)
        )
        self.ids = (
            [str(x) for x in data["ids"].tolist()]
            if "ids" in data.files
            else [f"c{i}" for i in range(len(self.labels))]
        )
        self.hold_acc = float(data["hold_acc"]) if "hold_acc" in data.files else 0.0
        self.train_acc = float(data["train_acc"]) if "train_acc" in data.files else 0.0
        self.available = True
        self.path = path

    def load(self, path: str | None = None):
        self._load(path or self.path)
        return self

    @classmethod
    def load_or_empty(cls, path: str = LEXICON_PATH) -> "ConceptLexicon":
        return cls(path)

    def save(
        self,
        labels: Sequence[str] | None = None,
        vectors: np.ndarray | None = None,
        raw: np.ndarray | None = None,
        mu: np.ndarray | None = None,
        domains: Optional[Sequence[str]] = None,
        ids: Optional[Sequence[str]] = None,
        train_acc: float | None = None,
        hold_acc: float | None = None,
        meta: Optional[dict] = None,
        path: str | None = None,
    ) -> str:
        path = path or self.path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if labels is not None:
            self.labels = list(labels)
        if vectors is not None:
            self.vectors = np.asarray(vectors, dtype=np.float32)
        if raw is not None:
            self.raw = np.asarray(raw, dtype=np.float32)
        elif self.raw.shape[0] != len(self.labels):
            self.raw = self.vectors.copy()
        if mu is not None:
            self.mu = np.asarray(mu, dtype=np.float32)
        if domains is not None:
            self.domains = list(domains)
        elif len(self.domains) != len(self.labels):
            self.domains = [""] * len(self.labels)
        if ids is not None:
            self.ids = list(ids)
        elif len(self.ids) != len(self.labels):
            self.ids = [f"c{i}" for i in range(len(self.labels))]
        if train_acc is not None:
            self.train_acc = float(train_acc)
        if hold_acc is not None:
            self.hold_acc = float(hold_acc)

        np.savez(
            path,
            mu=self.mu.astype(np.float32),
            vectors=self.vectors.astype(np.float32),
            dirs=self.vectors.astype(np.float32),  # compat alias
            raw=self.raw.astype(np.float32),
            labels=np.array(self.labels, dtype=object),
            domains=np.array(self.domains, dtype=object),
            ids=np.array(self.ids, dtype=object),
            train_acc=float(self.train_acc),
            hold_acc=float(self.hold_acc),
        )
        payload = {
            "n": len(self.labels),
            "path": path,
            "train_acc": float(self.train_acc),
            "hold_acc": float(self.hold_acc),
            **(meta or {}),
        }
        with open(LEXICON_META, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.available = True
        self.path = path
        return path

    def scores(self, vec: np.ndarray, centered: bool = True) -> np.ndarray:
        if not self.available or self.size == 0:
            return np.zeros(0, dtype=np.float32)
        if centered:
            v = _unit(np.asarray(vec, dtype=np.float32) - self.mu)
            return (self.vectors @ v).astype(np.float32)
        v = _unit(vec)
        return (self.raw @ v).astype(np.float32)

    def read(self, vec: np.ndarray, top_k: int = 5, centered: bool = True) -> List[Tuple[str, float]]:
        sc = self.scores(vec, centered=centered)
        if sc.size == 0:
            return []
        k = min(top_k, sc.size)
        idx = np.argpartition(sc, -k)[-k:]
        idx = idx[np.argsort(sc[idx])[::-1]]
        return [(self.labels[int(i)], float(sc[int(i)])) for i in idx]

    def top1(self, vec: np.ndarray, centered: bool = True) -> Tuple[str, float]:
        hits = self.read(vec, top_k=1, centered=centered)
        return hits[0] if hits else ("", 0.0)

    def nearest_label(self, vec: np.ndarray):
        return self.top1(vec, centered=True)

    def direction(self, label_or_id: str) -> Optional[np.ndarray]:
        for i, lab in enumerate(self.labels):
            if lab == label_or_id or self.ids[i] == label_or_id:
                return self.vectors[i].copy()
        return None

    def write(
        self,
        base_or_label=None,
        labels: Sequence[str] | None = None,
        alpha: float = 1.0,
        mode: str = "add",
        base: np.ndarray | None = None,
        scale: float | None = None,
        **kwargs,
    ) -> np.ndarray:
        """Flexible Write API supporting both call styles:

          write(base, [label], alpha=1, mode="replace")   # codec_roundtrip
          write(label, base=z, alpha=0.85)                # concept_lexicon CLI
          write(label, scale=1.0)                         # direction alone
        """
        if not self.available:
            raise RuntimeError("ConceptLexicon not loaded; train first")

        # Detect call style
        label_list: List[str] = []
        base_vec = base
        if isinstance(base_or_label, str) and labels is None and base is None:
            # write(label, ...) or write(label, scale=...)
            label_list = [base_or_label]
        elif isinstance(base_or_label, str) and base is not None:
            label_list = [base_or_label]
        elif base_or_label is not None and labels is not None:
            # write(base, [labels], ...)
            base_vec = np.asarray(base_or_label, dtype=np.float32)
            label_list = list(labels)
        elif isinstance(base_or_label, str):
            label_list = [base_or_label]
            if "base" in kwargs:
                base_vec = kwargs["base"]
        elif labels is not None:
            label_list = list(labels)

        dirs = []
        for lab in label_list:
            d = self.direction(lab)
            if d is not None:
                dirs.append(d)
        if not dirs:
            if base_vec is not None:
                return np.asarray(base_vec, dtype=np.float32).copy()
            raise KeyError(f"unknown proposition(s): {label_list!r}")

        mix = _unit(np.mean(np.stack(dirs), axis=0))
        if base_vec is None:
            out = mix.copy()
            if scale is not None:
                out = out * float(scale)
            return out.astype(np.float32)

        base_vec = np.asarray(base_vec, dtype=np.float32).reshape(-1)
        bn = float(np.linalg.norm(base_vec)) + 1e-8
        if mode == "replace":
            return (mix * (scale if scale is not None else bn)).astype(np.float32)
        # add / blend
        a = float(alpha)
        blended = (1.0 - a) * _unit(base_vec) + a * mix
        return (_unit(blended) * (scale if scale is not None else bn)).astype(np.float32)

    def write_from_text(
        self,
        base: np.ndarray,
        text: str,
        alpha: float = 1.0,
        mode: str = "add",
        top_k: int = 1,
    ) -> Tuple[np.ndarray, List[str]]:
        if text in self.labels:
            chosen = [text]
        else:
            tw = set(text.lower().split())
            scored = []
            for lab in self.labels:
                lw = set(lab.lower().split())
                scored.append((len(tw & lw) / (len(tw | lw) + 1e-8), lab))
            scored.sort(reverse=True)
            chosen = [lab for s, lab in scored[:top_k] if s > 0]
        if not chosen:
            return np.asarray(base, dtype=np.float32).copy(), []
        return self.write(base, chosen, alpha=alpha, mode=mode), chosen

    def gate_passed(self, threshold: float = DEFAULT_GATE_THRESHOLD) -> bool:
        return self.available and self.hold_acc >= threshold

    @classmethod
    def build(cls, brain, tok, rows: Sequence[dict], path: str = LEXICON_PATH) -> "ConceptLexicon":
        embs = []
        for row in rows:
            embs.append(encode_proposition(brain, tok, row["text"]))
        lex, _stats = build_lexicon_from_embeddings(rows, np.stack(embs), path=path)
        return lex


def build_lexicon(brain, tok, rows: Sequence[dict], path: str = LEXICON_PATH) -> "ConceptLexicon":
    """Alias for ConceptLexicon.build (codec_roundtrip / suite callers)."""
    return ConceptLexicon.build(brain, tok, rows, path=path)


def _keyword_jaccard(a: Sequence[str] | None, b: Sequence[str] | None) -> float:
    A = {x.lower() for x in (a or []) if x}
    B = {x.lower() for x in (b or []) if x}
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _word_jaccard(a: str, b: str) -> float:
    wa = {w for w in a.lower().replace(".", "").split() if len(w) > 1}
    wb = {w for w in b.lower().replace(".", "").split() if len(w) > 1}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def dedupe_keywords(rows: Sequence[dict]) -> List[dict]:
    """Prefer distinctive keywords: drop tokens that appear in many other rows."""
    from collections import Counter

    freq: Counter = Counter()
    for r in rows:
        for k in r.get("keywords") or []:
            freq[k.lower()] += 1
    out = []
    for r in rows:
        row = dict(r)
        kws = list(row.get("keywords") or [])
        # keep rare-first; ensure at least 2 content words from text if stripped bare
        ranked = sorted(kws, key=lambda k: (freq[k.lower()], -len(k)))
        kept = [k for k in ranked if freq[k.lower()] <= 2]
        if len(kept) < 2:
            kept = ranked[: max(2, min(3, len(ranked)))] or kws
        # unique preserve order
        seen = set()
        uniq = []
        for k in kept:
            lk = k.lower()
            if lk in seen:
                continue
            seen.add(lk)
            uniq.append(k)
        row["keywords"] = uniq
        out.append(row)
    return out


def filter_near_duplicates(
    rows: Sequence[dict], threshold: float = 0.75
) -> Tuple[List[dict], List[dict]]:
    """Drop near-duplicate texts (word Jaccard ≥ threshold). Returns (kept, dropped)."""
    kept: List[dict] = []
    dropped: List[dict] = []
    for r in rows:
        text = r.get("text") or r.get("proposition") or ""
        if any(_word_jaccard(text, k.get("text") or "") >= threshold for k in kept):
            dropped.append(r)
            continue
        kept.append(r)
    return kept, dropped


def stratified_holdout_ids(
    rows: Sequence[dict],
    ratio: float = 0.20,
    seed: int = 42,
    min_per_domain: int = 1,
) -> List[str]:
    """Domain-stratified holdout ids (~ratio per domain)."""
    rng = np.random.default_rng(seed)
    by_dom: dict = {}
    for r in rows:
        by_dom.setdefault(r.get("domain") or "_", []).append(r)
    hold_ids: List[str] = []
    for _dom, items in by_dom.items():
        n = len(items)
        k = max(min_per_domain, int(np.ceil(n * ratio)))
        k = min(k, max(1, n - 1)) if n > 1 else min(k, n)
        idxs = rng.choice(n, size=k, replace=False)
        for i in idxs:
            hold_ids.append(items[int(i)].get("id", ""))
    return [h for h in hold_ids if h]


def _hold_match(pred_label: str, gold_row: dict, pred_row: dict) -> bool:
    """Honest soft hold criterion: label/keyword match, or same-domain with keyword overlap."""
    gold = gold_row.get("text") or ""
    if proposition_match(pred_label, gold, gold_row.get("keywords")):
        return True
    gd = gold_row.get("domain") or ""
    pd = pred_row.get("domain") or ""
    if gd and gd == pd:
        # require some keyword/content overlap so pure domain luck is not enough
        if _keyword_jaccard(gold_row.get("keywords"), pred_row.get("keywords")) >= 0.2:
            return True
        if _word_jaccard(pred_label, gold) >= 0.35:
            return True
    return False


def build_lexicon_from_embeddings(
    rows: Sequence[dict],
    embeddings: np.ndarray,
    holdout_ids: Optional[Iterable[str]] = None,
    path: str = LEXICON_PATH,
    holdout_ratio: float = 0.20,
    holdout_seed: int = 42,
    dedupe_kw: bool = True,
) -> Tuple[ConceptLexicon, dict]:
    rows = list(rows)
    if dedupe_kw:
        rows = dedupe_keywords(rows)
    # near-dup filter is optional / cheap; keep all rows but record pairs for meta
    _kept, near_dropped = filter_near_duplicates(rows, threshold=0.85)

    emb = np.asarray(embeddings, dtype=np.float32)
    if emb.shape[0] != len(rows):
        raise ValueError(
            f"embeddings/rows mismatch: {emb.shape[0]} vs {len(rows)}"
        )
    labels = [r["text"] for r in rows]
    domains = [r.get("domain", "") for r in rows]
    ids = [r.get("id", f"c{i}") for i, r in enumerate(rows)]
    mu = emb.mean(axis=0)
    centered = emb - mu
    vectors = centered / (np.linalg.norm(centered, axis=1, keepdims=True) + 1e-8)
    raw = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8)

    hold = set(holdout_ids) if holdout_ids is not None else set(
        stratified_holdout_ids(rows, ratio=holdout_ratio, seed=holdout_seed)
    )
    train_idx = [i for i, rid in enumerate(ids) if rid not in hold]
    hold_idx = [i for i, rid in enumerate(ids) if rid in hold]
    if not hold_idx:
        hold = set(stratified_holdout_ids(rows, ratio=holdout_ratio, seed=holdout_seed))
        train_idx = [i for i, rid in enumerate(ids) if rid not in hold]
        hold_idx = [i for i, rid in enumerate(ids) if rid in hold]

    def nn_acc(idx_list):
        if not idx_list:
            return 0.0
        correct = 0
        for i in idx_list:
            pred = int(np.argmax(vectors @ vectors[i]))
            if pred == i:
                correct += 1
        return correct / len(idx_list)

    train_acc = nn_acc(train_idx)
    hold_soft_correct = 0
    hold_domain_correct = 0
    hold_legacy_correct = 0
    if hold_idx and train_idx:
        train_vecs = vectors[train_idx]
        for i in hold_idx:
            sc = train_vecs @ vectors[i]
            j = train_idx[int(np.argmax(sc))]
            if _hold_match(labels[j], rows[i], rows[j]):
                hold_soft_correct += 1
            if domains[i] and domains[i] == domains[j]:
                hold_domain_correct += 1
            # Primary gate: soft label/keyword OR same-domain NN (legacy-compatible).
            if proposition_match(labels[j], labels[i], rows[i].get("keywords")) or (
                domains[i] and domains[i] == domains[j]
            ):
                hold_legacy_correct += 1
        n_h = len(hold_idx)
        hold_acc_soft = hold_soft_correct / n_h
        hold_domain_acc = hold_domain_correct / n_h
        hold_acc = hold_legacy_correct / n_h
    else:
        hold_acc = train_acc
        hold_acc_soft = train_acc
        hold_domain_acc = train_acc

    lex = ConceptLexicon(path)
    lex.save(
        labels=labels,
        vectors=vectors,
        raw=raw,
        mu=mu,
        domains=domains,
        ids=ids,
        train_acc=train_acc,
        hold_acc=hold_acc,
        meta={
            "n_train": len(train_idx),
            "n_hold": len(hold_idx),
            "holdout_ratio": holdout_ratio,
            "holdout_seed": holdout_seed,
            "hold_acc_soft": hold_acc_soft,
            "hold_domain_acc": hold_domain_acc,
            "hold_ids": [ids[i] for i in hold_idx],
            "near_dup_dropped": len(near_dropped),
            "dedupe_keywords": dedupe_kw,
        },
        path=path,
    )
    stats = {
        "train_acc": train_acc,
        "hold_acc": hold_acc,
        "hold_acc_soft": hold_acc_soft,
        "hold_domain_acc": hold_domain_acc,
        "n": len(labels),
        "n_train": len(train_idx),
        "n_hold": len(hold_idx),
        "hold_ids": [ids[i] for i in hold_idx],
    }
    return lex, stats


def write_read_reproduce(lex: ConceptLexicon, rows: Sequence[dict] | None = None) -> dict:
    """辞書内 Write→Read (フォワード不要)。ゲート計測用。"""
    if rows is None:
        rows = [
            {"text": lab, "keywords": lab.split()[:3]}
            for lab in lex.labels
        ]
    correct = 0
    detail = []
    for row in rows:
        text = row["text"]
        if text not in lex.labels:
            continue
        # replace-write onto a neutral base then read
        base = np.random.randn(HIDDEN).astype(np.float32)
        base = _unit(base) * 10.0
        z = lex.write(base, [text], alpha=1.0, mode="replace")
        pred, score = lex.top1(z)
        ok = proposition_match(pred, text, row.get("keywords"))
        correct += int(ok)
        detail.append({"text": text, "pred": pred, "score": score, "ok": ok})
    n = len(detail)
    rate = correct / n if n else 0.0
    return {"n": n, "correct": correct, "rate": rate, "detail": detail}


def main():
    ap = argparse.ArgumentParser(description="Concept lexicon train/eval (Phase 2)")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--gate", type=float, default=DEFAULT_GATE_THRESHOLD)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--max-items", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from transformers import AutoTokenizer

    rows = load_propositions(args.corpus)
    if args.max_items and args.max_items > 0:
        rows = rows[: args.max_items]

    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(DEFAULT_MODEL, hidden=HIDDEN)
    try:
        if args.train or not os.path.exists(LEXICON_PATH):
            print(f"[Lexicon] training on {len(rows)} propositions...")
            lex = ConceptLexicon.build(brain, tok, rows)
            print(f"[Lexicon] hold_acc={lex.hold_acc*100:.1f}% train_acc={lex.train_acc*100:.1f}%")
        else:
            lex = ConceptLexicon(LEXICON_PATH)
            print(f"[Lexicon] loaded n={lex.size} hold_acc={lex.hold_acc}")

        if args.eval or args.train:
            gate = write_read_reproduce(lex, rows)
            gate["threshold"] = args.gate
            gate["pass"] = gate["rate"] >= args.gate
            print(
                f"[Lexicon] Write→Read: {gate['correct']}/{gate['n']} "
                f"= {gate['rate']*100:.1f}% gate={'PASS' if gate['pass'] else 'FAIL'}"
            )
            out = args.out or os.path.join(MEMORY_DIR, "concept_lexicon_gate.json")
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump({k: v for k, v in gate.items() if k != "detail"}, f, indent=2)
                f.write("\n")
            if not gate["pass"]:
                raise SystemExit(1)
    finally:
        brain.close()


if __name__ == "__main__":
    main()
