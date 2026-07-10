"""
space_council.py — HF Spaces 用の評議会コア (Qwen 0.5B のみ / CPU)
====================================================================
verantyx_council.Council.deliberate と同じ数学 (実フォワード、共鳴、
合意ベクトル、仮想トークン注入、摂動テスト) を、可視化のための
構造化イベントを yield する形に組み替えたもの。エスカレーションは
0.5B 単独構成のため存在しない。それ以外は本物の実装のミラー。

イベント (dict):
  status / round_start / opinion / consensus / inject / perturb /
  concepts / answer / baseline / done / error
"""
import os
import time

import json

import numpy as np

from verantyx_mind import HIDDEN, JGenDict, RustBrain

MODEL = os.environ.get("JGEN_MODEL", "/app/converted_models/qwen05b_full.jgen")


def _sidecar():
    try:
        with open(MODEL + ".meta.json") as f:
            return json.load(f)
    except OSError:
        return {}


_META = _sidecar()
TOKENIZER = (os.environ.get("JGEN_TOKENIZER")
             or _META.get("tokenizer") or "Qwen/Qwen2.5-0.5B-Instruct")
MODEL_HIDDEN = int(_META.get("hidden") or HIDDEN)

# 本体 verantyx_council.ROLES と同一
ROLES = [
    ("Commander", "You lead this analysis. State the single decisive answer.", 0.7),
    ("Scout-A",   "Explore alternative interpretations and hidden assumptions.", 1.3),
    ("Scout-B",   "Consider the opposite conclusion and test it.", 1.3),
    ("Worker-1",  "Work through the problem step by step precisely.", 0.7),
    ("Worker-2",  "Verify the reasoning and correct any mistake.", 0.7),
]

# 6軸のアンカー例文 (起動時に実フォワードで軸方向を実測する)
AXIS_SEEDS = {
    "Logic":    ["If A implies B and B implies C, then A implies C.",
                 "The proof follows by induction on n."],
    "Syntax":   ["def parse(tokens): return ast.walk(tree)",
                 "SELECT name FROM users WHERE age > 20;"],
    "Fact":     ["The capital of France is Paris.",
                 "Water boils at 100 degrees Celsius at sea level."],
    "Time":     ["Yesterday came before today, and tomorrow follows.",
                 "The meeting is scheduled for next Friday at noon."],
    "Creative": ["The moon whispered silver secrets to the sleeping sea.",
                 "Imagine a city where the streets rearrange themselves at dawn."],
    "Consensus": ["Everyone in the committee finally agreed on the plan.",
                  "The council reached a unanimous decision."],
}


def role_tokens(tok, directive, question):
    p = (f"<|im_start|>system\n{directive}<|im_end|>\n"
         f"<|im_start|>user\n{question}<|im_end|>\n"
         f"<|im_start|>assistant\nThe answer is")
    return tok.encode(p, add_special_tokens=False)


def dist_top1(dist):
    m = {}
    for s, w in dist:
        k = s.strip().lower()
        if k:
            m[k] = m.get(k, 0.0) + w
    return max(m.items(), key=lambda kv: kv[1])[0] if m else ""


def answers_agree(a, b):
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    return len(s) >= 3 and s in l


def token_cloud(tok, p, top_idx, k=5):
    order = top_idx[np.argsort(p[top_idx])[::-1]]
    out = []
    for i in order:
        s = tok.decode([int(i)]).strip()
        if s and not any(s == t for t, _ in out):
            out.append((s, float(p[i])))
        if len(out) >= k:
            break
    return out


def dist_from_vector(dictionary, tok, z, sem, top_k=48, temperature=1.0):
    lg = dictionary.logits(np.asarray(z, dtype=np.float32)) / temperature
    lg[dictionary.first_special:] = -np.inf
    if sem is not None:
        lg[~sem] = -np.inf
    lg -= lg[np.isfinite(lg)].max()
    p = np.exp(lg); p /= p.sum()
    top = np.argsort(p)[::-1][:top_k]
    out = [(tok.decode([int(i)]), float(p[i])) for i in top if p[i] > 1e-5]
    s = sum(w for _, w in out)
    return [(t, w / s) for t, w in out]


def dist_to_hidden(dictionary, tok, dist, base_norm):
    acc = None
    for s, w in dist:
        ids = tok.encode(s, add_special_tokens=False)
        if not ids:
            continue
        row = dictionary._lm_head_f16[ids].astype(np.float32).mean(axis=0)
        acc = w * row if acc is None else acc + w * row
    if acc is None:
        return None
    acc /= (np.linalg.norm(acc) + 1e-8)
    return (acc * base_norm).astype(np.float32)


def polish_answer(text):
    import re
    text = text.strip()
    if not text:
        return text
    lines = re.split(r"(?<=[。．.!?！？\n])", text)
    dedup, prev = [], None
    for s in lines:
        key = s.strip()
        if key and key == prev:
            continue
        dedup.append(s)
        prev = key or prev
    text = "".join(dedup).strip()
    if not text.endswith(tuple("。．.!?！？…」』】)”\"'`")):
        cut = max(text.rfind(c) for c in "。．.!?！？\n")
        if cut > len(text) * 0.3:
            text = text[:cut + 1]
    return text.strip()


class SpaceCouncil:
    """0.5B 単独の評議会。ロードは一度だけ、質問ごとに deliberate() を回す。"""

    def __init__(self):
        from transformers import AutoTokenizer
        t0 = time.time()
        self.tok = AutoTokenizer.from_pretrained(TOKENIZER)
        self.brain = RustBrain(MODEL, hidden=MODEL_HIDDEN)
        self.dict = JGenDict(MODEL)
        self.sem = self.dict.semantic_mask(self.tok)
        self.axes = self._measure_axes()
        self.load_s = time.time() - t0

    def _measure_axes(self):
        """6概念軸を実フォワードで実測する (アンカー例文の平均方向)。"""
        from verantyx_mind import embed_text
        dirs = []
        for name, seeds in AXIS_SEEDS.items():
            vs = [embed_text(self.brain, self.tok, s) for s in seeds]
            d = np.mean(vs, axis=0)
            dirs.append(d / (np.linalg.norm(d) + 1e-8))
        A = np.stack(dirs)             # (6, H)
        A -= A.mean(axis=0, keepdims=True)   # 共通成分 (文体) を除去して軸を立てる
        A /= np.linalg.norm(A, axis=1, keepdims=True) + 1e-8
        return A

    def axis_signature(self, z):
        zn = np.asarray(z, dtype=np.float32)
        zn = zn / (np.linalg.norm(zn) + 1e-8)
        sig = self.axes @ zn
        # 相対強度に正規化 (0..1)
        lo, hi = sig.min(), sig.max()
        return [round(float(v), 4) for v in (sig - lo) / (hi - lo + 1e-8)]

    # ── 3D投影: 意見ベクトル群のPCA基底 (質問ごとに固定) ──
    def _make_projector(self, vecs):
        M = np.stack(vecs)
        M = M - M.mean(axis=0, keepdims=True)
        try:
            _, _, vt = np.linalg.svd(M, full_matrices=False)
            basis = vt[:3]
            if basis.shape[0] < 3:
                raise np.linalg.LinAlgError
        except np.linalg.LinAlgError:
            rng = np.random.default_rng(7)
            basis = rng.standard_normal((3, M.shape[1]))
        basis = basis / (np.linalg.norm(basis, axis=1, keepdims=True) + 1e-8)
        center = np.stack(vecs).mean(axis=0)

        def project(z):
            p = basis @ (np.asarray(z, dtype=np.float32) - center)
            n = np.linalg.norm(p) + 1e-8
            return [round(float(v / max(n, 1e-8) * min(n, 3.0)), 4) for v in p]
        return project

    def deliberate(self, question, max_rounds=3):
        """イベントを yield するジェネレータ。数学は本体 Council.deliberate のミラー。"""
        tok, brain, dic, sem = self.tok, self.brain, self.dict, self.sem
        t_start = time.time()
        yield {"type": "status", "msg": "ラウンド0: 各役割が独立に実フォワード中 (テキスト生成なし)"}

        role_toks = {n: role_tokens(tok, d, question) for n, d, _ in ROLES}
        opinions = {}
        for n, _, _ in ROLES:
            opinions[n] = brain.encode(role_toks[n])
        intent = opinions["Commander"].copy()
        intent_n = intent / (np.linalg.norm(intent) + 1e-8)
        base_norm = float(np.linalg.norm(intent)) + 1e-8
        project = self._make_projector(list(opinions.values()))

        consensus, consensus_dist = None, None
        prev_top1 = None
        perturb_done = False
        history = []
        for rnd in range(1, max_rounds + 1):
            yield {"type": "round_start", "round": rnd}
            vecs, weights, confident = [], [], []
            for name, _, temp in ROLES:
                z = opinions[name]
                zn = z / (np.linalg.norm(z) + 1e-8)
                _, entropy, p, top = dic.resonance(z, temperature=temp, mask=sem)
                cloud = token_cloud(tok, p, top, k=4)
                coherence = float(zn @ intent_n)
                w = max(coherence, 0.05) / (1.0 + entropy)
                vecs.append(zn); weights.append(w)
                if entropy < 4.0:
                    confident.append(dist_top1([(s, pr) for s, pr in cloud]))
                yield {"type": "opinion", "round": rnd, "name": name,
                       "entropy": round(float(entropy), 2),
                       "coherence": round(coherence, 3),
                       "weight": round(float(w), 4),
                       "top": [[s, round(pr, 3)] for s, pr in cloud],
                       "pos": project(z)}

            W = np.array(weights); W /= W.sum()
            consensus = sum(w * v for w, v in zip(W, vecs))
            consensus = consensus / (np.linalg.norm(consensus) + 1e-8) * base_norm
            consensus_dist = dist_from_vector(dic, tok, consensus, sem)
            consensus_top1 = dist_top1(consensus_dist)

            M = np.stack(vecs)
            agree_cos = float((M @ M.T)[np.triu_indices(len(vecs), 1)].mean())
            unanimous = bool(confident) and all(
                answers_agree(t, consensus_top1) for t in confident)
            _, c_entropy, p, top = dic.resonance(consensus, temperature=0.9, mask=sem)
            c_cloud = token_cloud(tok, p, top, k=4)
            history.append({"round": rnd, "agreement": agree_cos, "top1": consensus_top1})
            yield {"type": "consensus", "round": rnd,
                   "agreement": round(agree_cos, 4),
                   "entropy": round(float(c_entropy), 2),
                   "unanimous": unanimous, "top1": consensus_top1,
                   "top": [[s, round(pr, 3)] for s, pr in c_cloud],
                   "pos": project(consensus),
                   "axes": self.axis_signature(consensus)}

            stable = prev_top1 is not None and consensus_top1 == prev_top1
            prev_top1 = consensus_top1
            if unanimous or stable:
                # 本体と同じ摂動テスト: 対抗馬を混ぜた偽合意を注入して耐性を試す
                if not perturb_done and rnd < max_rounds:
                    perturb_done = True
                    yield {"type": "status",
                           "msg": "収束を検出 → 摂動テスト: 対抗馬を強めた偽の合意を全役割に注入"}
                    recovered, drift, lured = self._perturb(
                        question, consensus, consensus_dist, role_toks, base_norm)
                    yield {"type": "perturb", "round": rnd,
                           "recovered": recovered, "drift_cos": round(drift, 4),
                           "lured_to": lured}
                    if recovered:
                        break
                else:
                    break
            if rnd == max_rounds:
                break
            # 合意を仮想トークンとして全役割へ注入 (ベクトル通信そのもの)
            e_consensus = dic.to_embedding(consensus, mask=sem)
            yield {"type": "inject", "round": rnd,
                   "msg": "合意ベクトルを仮想トークン化して全役割の次フォワードへ注入"}
            for name, _, _ in ROLES:
                opinions[name] = brain.encode_soft(e_consensus[None, :], role_toks[name])

        # 概念翻訳
        _, _, p, top = dic.resonance(consensus, temperature=1.0, mask=sem)
        concepts, seen = [], set()
        for s, _ in token_cloud(tok, p, top, k=24):
            key = s.strip().lower().lstrip("-_")
            if len(s) >= 2 and key not in seen and any(
                    c.isalnum() or ord(c) > 0x2E80 for c in s):
                seen.add(key)
                concepts.append(s.strip())
            if len(concepts) >= 6:
                break
        yield {"type": "concepts", "concepts": concepts,
               "deliberation_s": round(time.time() - t_start, 1),
               "history": [{"round": h["round"],
                            "agreement": round(h["agreement"], 3)} for h in history]}

        # 発話 (本体の router speak と同じ)
        yield {"type": "status", "msg": "発話フェーズ: 合意の概念を条件にテキスト化 (ここで初めてトークン生成)"}
        t0 = time.time()
        sys_p = "You are a helpful assistant."
        if concepts:
            sys_p += " Council consensus concepts: " + ", ".join(concepts) + "."
        pr = (f"<|im_start|>system\n{sys_p}<|im_end|>\n"
              f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n")
        out = brain.generate(tok.encode(pr, add_special_tokens=False), 140)
        answer = polish_answer(tok.decode(out, skip_special_tokens=True).strip())
        yield {"type": "answer", "text": answer,
               "speak_s": round(time.time() - t0, 1),
               "total_s": round(time.time() - t_start, 1)}

    def _perturb(self, question, consensus, consensus_dist, role_toks, base_norm):
        top1 = dist_top1(consensus_dist)
        rival = next((c for c in consensus_dist[1:]
                      if not answers_agree(dist_top1([c]), top1)), None)
        if rival is None:
            return True, 1.0, None
        z_rival = dist_to_hidden(self.dict, self.tok, [rival], base_norm)
        if z_rival is None:
            return True, 1.0, None
        cn = consensus / (np.linalg.norm(consensus) + 1e-8)
        rn = z_rival / (np.linalg.norm(z_rival) + 1e-8)
        lie = 0.4 * cn + 0.6 * rn
        lie = lie / (np.linalg.norm(lie) + 1e-8) * base_norm
        e_lie = self.dict.to_embedding(lie, mask=self.sem)
        test_vecs = []
        for name, _, _ in ROLES:
            z = self.brain.encode_soft(e_lie[None, :], role_toks[name])
            test_vecs.append(z / (np.linalg.norm(z) + 1e-8))
        test_consensus = np.mean(test_vecs, axis=0)
        test_consensus = test_consensus / (np.linalg.norm(test_consensus) + 1e-8) * base_norm
        drift = float((test_consensus / (np.linalg.norm(test_consensus) + 1e-8)) @ cn)
        test_top1 = dist_top1(dist_from_vector(self.dict, self.tok, test_consensus, self.sem))
        recovered = answers_agree(test_top1, top1)
        return recovered, drift, test_top1

    def baseline(self, question, max_new=140):
        """比較用: 同じ 0.5B に評議会なしで直接生成させる。"""
        t0 = time.time()
        pr = (f"<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n"
              f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n")
        out = self.brain.generate(self.tok.encode(pr, add_special_tokens=False), max_new)
        text = polish_answer(self.tok.decode(out, skip_special_tokens=True).strip())
        return {"type": "baseline", "text": text,
                "elapsed_s": round(time.time() - t0, 1), "tokens": len(out)}
