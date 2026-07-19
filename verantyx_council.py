"""
verantyx_council.py — ベクトル評議会オーケストレーター
==============================================================================

擬似CoTではなく、複数の役割エージェントが「思考ベクトルそのもの」を交換しながら
議論ラウンドを重ねて思考を深める。テキストによる伝言ゲームは一切行わない。

中核メカニズム (全て実演算):
  1. 各役割は短い役割指示つきで質問をエンコードする (全層の実フォワード)
  2. 合意ベクトル z は lm_head 射影→埋め込み再合成で「仮想トークン」となり、
     次ラウンドの各役割のフォワードパスへ直接注入される (encode_soft)
  3. Commander は各意見を評価 (意図との整合 × 確信度) して合意を更新
  4. 意見間の合意度が収束するか最大ラウンドで議論終了 -> Speaker が発話

ベクトル強奪 (Vector Hijack):
  大型モデルは「Thinking Process...」の長いおしゃべりを生成させず、
  回答スロート直後の隠れ状態を推論の途中で直接抜き取る (1フォワードのみ)。
  9Bでも数秒で議論に参加できる。

エスカレーション:
  auto モードでは 0.5B の評議会が合意に達しない時だけ、
  格上のモデル (jgenワーカー -> HF大型モデル) を遅延ロードして招集する。
  参加者は語彙分布インターリンガで交信するため、トークナイザも次元も
  アーキテクチャも異なるどんなモデルでも議論に参加できる。

思考の軌跡 (Thought Trace):
  各ラウンドの全意見ベクトルと合意ベクトルを永遠の記憶とは別の
  追記型ストアに保存。後から「あの時何を考えていたか」を
  ベクトルのまま再共鳴させて辿れる。

使い方:
  python3 verantyx_council.py --prompt "..." [--rounds auto|N] [--sage] [--no-escalate]
  python3 verantyx_council.py --traces            # 軌跡一覧
  python3 verantyx_council.py --trace <trace_id>  # 軌跡の再生
"""

import argparse
import json
import os
import re
import time
import uuid

import numpy as np

from verantyx_mind import (
    RustBrain, JGenDict, AxisAnchors, CortexMemory, AXIS_NAMES,
    DEFAULT_MODEL, TOKENIZER, HIDDEN, MEMORY_DIR, embed_text,
    token_cloud, bar, C_SYS, C_THINK, C_SPEAK, C_MEM, C_RESET,
)

C_CMD, C_SCOUT, C_WORK = "\033[91m", "\033[94m", "\033[92m"

TRACE_IDX = os.path.join(MEMORY_DIR, "traces.jsonl")
TRACE_VEC = os.path.join(MEMORY_DIR, "traces.vectors")

ROLES = [
    # (名前, 色, 役割指示, 共鳴温度)
    ("Commander", C_CMD,  "You lead this analysis. State the single decisive answer.", 0.7),
    ("Scout-A",   C_SCOUT, "Explore alternative interpretations and hidden assumptions.", 1.3),
    ("Scout-B",   C_SCOUT, "Consider the opposite conclusion and test it.", 1.3),
    ("Worker-1",  C_WORK,  "Work through the problem step by step precisely.", 0.7),
    ("Worker-2",  C_WORK,  "Verify the reasoning and correct any mistake.", 0.7),
]


def role_tokens(tok, directive, question):
    # 末尾を回答誘導 ("The answer is") にすることで、最終隠れ状態が
    # 「書き出しトークン」ではなく「答えの候補分布」を運ぶようにする
    p = (f"<|im_start|>system\n{directive}<|im_end|>\n"
         f"<|im_start|>user\n{question}<|im_end|>\n"
         f"<|im_start|>assistant\nThe answer is")
    return tok.encode(p, add_special_tokens=False)


# 会社型ベクトル役割 (NL 往復ではなく AbstractCanvas 合議用)
COMPANY_ROLES = [
    ("ceo", C_CMD,
     "You are the CEO. Decompose the task and state the decisive answer target.", 0.7),
    ("worker", C_WORK,
     "You are the worker. Solve the problem step by step and propose the answer.", 0.7),
    ("critic", C_SCOUT,
     "You are the critic. Attack the answer, find contradictions, propose rivals.", 1.2),
    ("integrator", C_CMD,
     "You are the integrator. Merge evidence into one coherent final answer.", 0.6),
]


def _looks_like_logic(question: str) -> bool:
    """logic / 演算系の粗い検出。intent 無しでも critic+decontam を必須化するため。"""
    q = (question or "").lower()
    keys = (
        "calculate", "compute", "how many", "how much", "equals", "equation",
        "logic", "if and only", "therefore", "prove", "modulo", "remainder",
        "足す", "引く", "掛け", "割り", "計算", "何個", "いくら", "論理",
        "+", "-", "*", "/", "=", "%",
    )
    if any(k in q for k in keys):
        return True
    # 数字が2つ以上 + 演算っぽい語
    nums = re.findall(r"\d+(?:\.\d+)?", q)
    return len(nums) >= 2 and any(w in q for w in ("cost", "gram", "times", "plus", "minus", "total"))


# ── 語彙分布インターリンガ (異モデル間のベクトル交信路) ─────────────────────────
# soft 注入前に落とす談話マーカー (内容質量を希釈する)
_DIST_STOP = frozenset({
    "the", "this", "that", "there", "these", "those", "yes", "no", "true", "false",
    "therefore", "based", "a", "an", "it", "i", "as", "what", "hello", "please",
    "in", "where", "and", "or", "is", "are", "was", "were", "be", "to", "of", "for",
    "on", "at", "with", "by", "not", "you", "she", "he", "we", "they", "my", "your",
    "answer", "sure", "none", "still", "itself", "directly", "also", "already",
    "correct", "however", "so", "too", "just", "one", "two", "x",
})


def dist_from_vector(dictionary, tok, z, sem, top_k=48, temperature=1.0):
    """思考ベクトル -> 語彙分布 [(文字列, 確率), ...]。
    単一テキストへ潰さず、候補の不確実性ごと異モデルへ運ぶ。"""
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


def sharpen_dist(dist, top_n=16, min_chars=3):
    """談話マーカーを落とし、内容候補へ質量を再正規化する。"""
    import re
    kept = []
    seen = set()
    for s, w in dist or []:
        t = (s or "").strip()
        if not t:
            continue
        alnum = re.sub(r"[^A-Za-z0-9]", "", t)
        if len(alnum) < min_chars:
            continue
        key = alnum.lower()
        if key in _DIST_STOP or t.lower() in _DIST_STOP:
            continue
        if key in seen:
            # 重複は質量だけ加算
            for i, (ss, ww) in enumerate(kept):
                if re.sub(r"[^A-Za-z0-9]", "", ss).lower() == key:
                    kept[i] = (ss, ww + float(w))
                    break
            continue
        seen.add(key)
        kept.append((s, float(w)))
        if len(kept) >= top_n:
            break
    if not kept:
        kept = list(dist[:6]) if dist else []
    total = sum(w for _, w in kept) or 1.0
    kept.sort(key=lambda x: -x[1])
    return [(t, w / total) for t, w in kept]


def dist_mass_overlap(a, b, top_n=8):
    """上位候補集合の質量重なり (0..1)。reinfer 後退検出用。"""
    if not a or not b:
        return 0.0
    import re

    def _norm(s):
        return re.sub(r"[^A-Za-z0-9]", "", (s or "")).lower()

    ma = {_norm(s): float(w) for s, w in a[:top_n] if _norm(s)}
    mb = {_norm(s): float(w) for s, w in b[:top_n] if _norm(s)}
    if not ma or not mb:
        return 0.0
    keys = set(ma) | set(mb)
    inter = sum(min(ma.get(k, 0.0), mb.get(k, 0.0)) for k in keys)
    union = sum(max(ma.get(k, 0.0), mb.get(k, 0.0)) for k in keys) or 1.0
    return float(inter / union)


def protect_dist_mass(old_dist, new_dist, min_overlap=0.25, blend=0.55):
    """reinfer 後に旧候補質量が大きく落ちたら旧分布を混ぜて保護する。"""
    if not old_dist:
        return list(new_dist or [])
    if not new_dist:
        return list(old_dist)
    ov = dist_mass_overlap(old_dist, new_dist)
    if ov >= min_overlap:
        return list(new_dist)
    acc = {}
    for s, w in old_dist:
        k = (s or "").strip()
        if k:
            acc[k] = acc.get(k, 0.0) + float(w) * blend
    for s, w in new_dist:
        k = (s or "").strip()
        if k:
            acc[k] = acc.get(k, 0.0) + float(w) * (1.0 - blend)
    total = sum(acc.values()) or 1.0
    return sorted(((k, v / total) for k, v in acc.items()), key=lambda x: -x[1])[:48]


def soft_probe_tokens(tok, kind="none"):
    """encode_soft 後段キャリア。長い ChatML は soft 内容を洗い流すので短く保つ。"""
    if kind in (None, "none", ""):
        return []
    if kind == "answer":
        return tok.encode("The answer is", add_special_tokens=False)
    if kind == "fact":
        return tok.encode("The fact is", add_special_tokens=False)
    if kind == "assistant":
        return tok.encode("<|im_start|>assistant\n", add_special_tokens=False)
    return tok.encode(str(kind), add_special_tokens=False)


def dist_to_soft_sequence(dist, tok, embed_rows, max_soft=16, sharpen=True):
    """語彙分布 -> 仮想トークン列 (各語のトークン埋め込みを展開)。

    単一ベクトルへ平均すると内容が消える。トークン列のまま inject する。
    長い内容語を先に並べ、短い断片でスロットを埋めない。
    """
    use = sharpen_dist(dist, top_n=max(16, max_soft)) if sharpen else list(dist or [])
    # 内容語長で安定ソート (質量は維持、長い語を優先展開)
    def _alen(s):
        return len(re.sub(r"[^A-Za-z0-9]", "", (s or "")))

    ranked = sorted(use, key=lambda sw: (-_alen(sw[0]), -float(sw[1])))
    vecs = []
    rows = np.asarray(embed_rows)
    seen_ids = set()
    for s, _w in ranked:
        ids = tok.encode(s, add_special_tokens=False)
        for i in ids:
            if i < 0 or i >= len(rows) or i in seen_ids:
                continue
            seen_ids.add(i)
            vecs.append(np.asarray(rows[i], dtype=np.float32))
            if len(vecs) >= max_soft:
                break
        if len(vecs) >= max_soft:
            break
    if not vecs:
        e = dist_to_soft_numpy(use or dist, tok, embed_rows, sharpen=False)
        return e[None, :]
    return np.stack(vecs, axis=0)


def dist_to_soft_numpy(dist, tok, embed_rows, sharpen=True, top_n=8):
    """語彙分布 -> このモデルの埋め込み空間上の仮想トークン (単一・後方互換)。

    既定で sharpen。単一ブレンドより dist_to_soft_sequence を推奨。
    """
    use = sharpen_dist(dist, top_n=top_n) if sharpen else list(dist or [])
    acc = None
    wsum = 0.0
    nsum = 0.0
    for s, w in use:
        ids = tok.encode(s, add_special_tokens=False)
        if not ids:
            continue
        rows = np.asarray(embed_rows)[ids].astype(np.float32)
        r = rows.mean(axis=0)
        acc = w * r if acc is None else acc + w * r
        nsum += w * float(np.linalg.norm(rows, axis=1).mean())
        wsum += w
    if acc is None:
        # 空分布フォールバック
        dim = int(np.asarray(embed_rows).shape[1])
        return np.zeros(dim, dtype=np.float32)
    e = acc / (wsum + 1e-8)
    e *= (nsum / (wsum + 1e-8)) / (np.linalg.norm(e) + 1e-8)
    return e.astype(np.float32)


def encode_with_dist_soft(brain, tok, embed_rows, dist, probe="none", max_soft=16,
                          dictionary=None, hidden_blend=0.35):
    """sharpen → soft 列 → encode_soft。council / codec 共通入口。

    hidden_blend>0 かつ dictionary があるとき、同 dist の dist_to_hidden と
    正規化ブレンドして内容質量を保つ (長いキャリア無しでも 0%→数十% の差が出る)。
    """
    use = sharpen_dist(dist)
    soft = dist_to_soft_sequence(use, tok, embed_rows, max_soft=max_soft, sharpen=False)
    carrier = soft_probe_tokens(tok, probe)
    z_soft = brain.encode_soft(soft, carrier)
    if not hidden_blend or dictionary is None or not use:
        return z_soft
    try:
        base_norm = float(np.linalg.norm(z_soft)) + 1e-8
        z_hid = dist_to_hidden(dictionary, tok, use, base_norm)
        if z_hid is None:
            return z_soft
        a = np.asarray(z_soft, dtype=np.float32)
        b = np.asarray(z_hid, dtype=np.float32)
        a = a / (np.linalg.norm(a) + 1e-8)
        b = b / (np.linalg.norm(b) + 1e-8)
        # hidden_blend = dist_to_hidden 側の重み
        mix = (1.0 - float(hidden_blend)) * a + float(hidden_blend) * b
        return (mix * base_norm).astype(np.float32)
    except Exception:
        return z_soft


def dist_to_hidden(dictionary, tok, dist, base_norm):
    """語彙分布 -> ルーター隠れ空間の意見ベクトル。
    lm_head の行は各トークンの分類方向なので、その加重合成は
    「この分布を主張する」隠れ状態になる。"""
    acc = None
    for s, w in dist:
        ids = tok.encode(s, add_special_tokens=False)
        if not ids:
            continue
        # 複数トークン語 ("Mars"->"M"+"ars") は全行の平均で方向を取る
        row = dictionary._lm_head_f16[ids].astype(np.float32).mean(axis=0)
        acc = w * row if acc is None else acc + w * row
    if acc is None:
        return None  # 分布が空 (外部参加者の応答不良など)
    acc /= (np.linalg.norm(acc) + 1e-8)
    return (acc * base_norm).astype(np.float32)


def dist_entropy(dist):
    return float(-sum(w * np.log2(w + 1e-12) for _, w in dist))


# ── スマート発話 (トークン上限の自動化) ──────────────────────────────────────
# 固定上限で文が途切れるのを防ぐ。EOS が真の終了シグナルであり、上限は
# 暴走防止の天井にすぎない。天井に当たった場合は文の境界まで戻して返す。
AUTO_CEILING = 1536      # 大型モデル (EOSで自然に止まる) の安全天井
AUTO_CEILING_SMALL = 768  # 0.5B (EOSを出し損ねて反復しがち) の安全天井
_SENT_END = tuple("。．.!?！？…」』】)”\"'`")


def resolve_tokens(max_new, small=False):
    """'auto' -> 天井値 / 数値 -> そのまま。"""
    if max_new in (None, "auto"):
        return AUTO_CEILING_SMALL if small else AUTO_CEILING
    return int(max_new)


def polish_answer(text):
    """スマート整形: 途切れた末尾を文境界まで戻し、反復した文を畳む。"""
    text = text.strip()
    if not text:
        return text
    # 1) 隣接反復の除去 (小型モデルが同じ文を繰り返すパターン)
    lines = re.split(r"(?<=[。．.!?！？\n])", text)
    dedup, prev = [], None
    for s in lines:
        key = s.strip()
        if key and key == prev:
            continue
        dedup.append(s)
        prev = key or prev
    text = "".join(dedup).strip()
    # 2) 文の途中で切れていたら最後の文境界まで戻す (全体が1文未満なら残す)
    if not text.endswith(_SENT_END):
        cut = max(text.rfind(c) for c in "。．.!?！？\n")
        if cut > len(text) * 0.3:
            text = text[:cut + 1]
    return text.strip()


def answers_agree(a, b):
    """回答文字列の一致判定。トークナイザ差でサブワードに割れるため
    ('mars' vs 'ars')、3文字以上の包含も一致とみなす。"""
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    return len(s) >= 3 and s in l


def dist_top1(dist):
    """回答分布の第一候補 (大文字小文字を正規化した文字列)。"""
    m = {}
    for s, w in dist:
        k = s.strip().lower()
        if k:
            m[k] = m.get(k, 0.0) + w
    if not m:
        return ""
    return max(m.items(), key=lambda kv: kv[1])[0]


def probs_to_dist(tok, p, top_k=32):
    """共鳴済み確率配列 -> 語彙分布 [(文字列, 確率), ...]。"""
    top = np.argsort(p)[::-1][:top_k]
    out = [(tok.decode([int(i)]), float(p[i])) for i in top if p[i] > 1e-5]
    s = sum(w for _, w in out) + 1e-12
    return [(t, w / s) for t, w in out]


# ── 評議会参加者 (異モデル対応) ────────────────────────────────────────────────
class JGenParticipant:
    """レジストリ上の任意の jgen モデルの参加者。整列行列は不要:
    語彙分布インターリンガで受信し、自空間の仮想トークンとして注入、
    自分の回答スロット隠れ状態 (=ベクトル強奪) を分布で返す。"""

    def __init__(self, reg_entry, directive="Give your independent expert judgment."):
        from transformers import AutoTokenizer
        self.name = reg_entry["name"]
        self.tok = AutoTokenizer.from_pretrained(reg_entry["tokenizer"])
        self.brain = RustBrain(reg_entry["jgen"], hidden=reg_entry.get("hidden") or HIDDEN)
        self.dict = JGenDict(reg_entry["jgen"])
        self.directive = directive
        self.sem = None
        # 圧迫時に合成済み重みキャッシュを解放できるように登録 (モデルは生きたまま)
        from memory_guard import GUARD
        GUARD.register_trimmable(f"jgen:{self.name}", self.brain.trim)

    def opine_dist(self, question, consensus_dist=None):
        if self.sem is None:
            self.sem = self.dict.semantic_mask(self.tok)
        toks = role_tokens(self.tok, self.directive, question)
        if consensus_dist is not None:
            e = dist_to_soft_numpy(consensus_dist, self.tok, self.dict._embed_f16)
            z = self.brain.encode_soft(e[None, :], toks)
        else:
            z = self.brain.encode(toks)
        return dist_from_vector(self.dict, self.tok, z, self.sem), ""

    def speak(self, question, concepts, max_new=48, brief=None):
        if brief is not None:
            sys_p = brief.system_prompt(for_api=False)
        else:
            sys_p = "You are a helpful assistant."
            if concepts:
                sys_p += " Council consensus concepts: " + ", ".join(concepts) + "."
        p = (f"<|im_start|>system\n{sys_p}<|im_end|>\n"
             f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n")
        out = self.brain.generate(self.tok.encode(p, add_special_tokens=False), max_new)
        return self.tok.decode(out, skip_special_tokens=True).strip()

    def close(self):
        self.brain.close()


class HFSage:
    """任意の HuggingFace モデルの参加者 (デフォルト: Ornith 9B / MPS)。
    ベクトル強奪モード: おしゃべり (Thinking Process...) を生成させず、
    回答スロット直後の隠れ状態を推論の途中で1フォワードだけ抜き取る。
    think_budget > 0 のときだけ内部潜考を許す。"""

    ORNITH = ("/Users/motonishikoudai/verantyx-cli/local_weights/"
              "models--deepreinforce-ai--Ornith-1.0-9B/snapshots/"
              "83dc1f5e24ef8527af019a6b3bf66ac0f1c2c999")

    def __init__(self, model_dir=None, name="ornith-9b", think_budget=0):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        self.torch = torch
        self.name = name
        model_dir = model_dir or self.ORNITH
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
            dtype = torch.float16
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            dtype = torch.float16
        else:
            self.device = torch.device("cpu")
            dtype = torch.float32
        print(f"{C_SYS}  [Sage] {name} をロード中 ({self.device.type}/{dtype})...{C_RESET}")
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_dir, dtype=dtype, low_cpu_mem_usage=True,
            attn_implementation="eager").to(self.device).eval()
        self.embed_w = self.model.get_input_embeddings().weight
        self._embed_rows = None
        self.think_budget = think_budget
        self.first_special = min(self.tok.vocab_size, self.model.config.vocab_size
                                 if hasattr(self.model.config, "vocab_size") else 10**9)

    def _prompt_embeds(self, question, consensus_dist):
        torch = self.torch
        msgs = [{"role": "user", "content": question}]
        text = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        ids = self.tok(text, return_tensors="pt").input_ids.to(self.device)
        e_ids = self.model.get_input_embeddings()(ids)
        if consensus_dist is not None:
            if self._embed_rows is None:
                self._embed_rows = self.embed_w.detach().float().cpu().numpy()
            e_soft = dist_to_soft_numpy(consensus_dist, self.tok, self._embed_rows)
            e_soft = torch.tensor(e_soft, dtype=e_ids.dtype, device=self.device).view(1, 1, -1)
            e_ids = torch.cat([e_soft, e_ids], dim=1)
        return e_ids

    def opine_dist(self, question, consensus_dist=None):
        """ベクトル強奪: 合意分布を注入した1フォワードで回答分布を抜き取る。"""
        torch = self.torch
        with torch.no_grad():
            e = self._prompt_embeds(question, consensus_dist)
            inner = ""
            if self.think_budget > 0:
                mask = torch.ones(e.shape[:2], dtype=torch.long, device=self.device)
                gen = self.model.generate(
                    inputs_embeds=e, attention_mask=mask,
                    max_new_tokens=self.think_budget, do_sample=False,
                    pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
                inner = self.tok.decode(gen[0], skip_special_tokens=True)
                e = torch.cat([e, self.model.get_input_embeddings()(gen)], dim=1)
            cue = self.tok("\nThe answer is", return_tensors="pt").input_ids.to(self.device)
            e2 = torch.cat([e, self.model.get_input_embeddings()(cue)], dim=1)
            mask2 = torch.ones(e2.shape[:2], dtype=torch.long, device=self.device)
            o = self.model(inputs_embeds=e2, attention_mask=mask2)
            lg = o.logits[0, -1].float().cpu().numpy()
        lg[self.first_special:] = -np.inf
        lg -= lg[np.isfinite(lg)].max()
        p = np.exp(lg); p /= p.sum()
        top = np.argsort(p)[::-1][:48]
        dist = [(self.tok.decode([int(i)]), float(p[i])) for i in top if p[i] > 1e-5]
        s = sum(w for _, w in dist)
        return [(t, w / s) for t, w in dist], inner

    def speak(self, question, concepts, max_new=60, brief=None):
        torch = self.torch
        if brief is not None:
            sys_p = brief.system_prompt(for_api=False)
        else:
            sys_p = "Answer concisely."
            if concepts:
                sys_p += " Council consensus concepts: " + ", ".join(concepts) + "."
        msgs = [{"role": "system", "content": sys_p},
                {"role": "user", "content": question}]
        text = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        enc = self.tok(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model.generate(**enc, max_new_tokens=max(max_new, 220), do_sample=False,
                                      pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
            cue = self.tok("\n\nFinal answer:", return_tensors="pt").input_ids.to(self.device)
            ids2 = torch.cat([out, cue], dim=1)
            mask2 = torch.ones_like(ids2)
            out2 = self.model.generate(input_ids=ids2, attention_mask=mask2,
                                       max_new_tokens=min(max(max_new, 32), 400),
                                       do_sample=False,
                                       pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
        ans = self.tok.decode(out2[0][ids2.shape[1]:], skip_special_tokens=True).strip()
        return ans.split("\n\n")[0].strip()

    def close(self):
        pass


# ── 思考の軌跡 (Thought Trace) ────────────────────────────────────────────────
class ThoughtTrace:
    """議論の全ベクトル (各役割の意見 + 合意) を追記保存する軌跡ストア。
    永遠の記憶 (CortexMemory) と対になり、記憶ノードから trace_id で遡れる。"""

    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._count = 0
        if os.path.exists(TRACE_VEC):
            self._count = os.path.getsize(TRACE_VEC) // (HIDDEN * 2)

    def put_vector(self, v):
        from verantyx_mind import fit_vec
        with open(TRACE_VEC, "ab") as f:
            f.write(fit_vec(v, HIDDEN).astype(np.float16).tobytes())
        self._count += 1
        return self._count - 1

    def get_vector(self, idx):
        with open(TRACE_VEC, "rb") as f:
            f.seek(idx * HIDDEN * 2)
            return np.frombuffer(f.read(HIDDEN * 2), dtype=np.float16).astype(np.float32)

    def save(self, record):
        with open(TRACE_IDX, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def list(self, limit=20):
        if not os.path.exists(TRACE_IDX):
            return []
        with open(TRACE_IDX) as f:
            recs = [json.loads(l) for l in f if l.strip()]
        return recs[-limit:]

    def load(self, trace_id):
        for rec in self.list(limit=10**6):
            if rec["trace_id"].startswith(trace_id):
                return rec
        return None


# ── 評議会オーケストレーター ──────────────────────────────────────────────────
class Council:
    """ルーター評議会 + エスカレーション + 軌跡 + 永遠の記憶を束ねる本体。
    MCP サーバーと CLI の両方から使われる。"""

    ENTROPY_CONVERGED = 3.0
    # 不確実性シグナル: 探索役 (Scout) が答えをロックできない (高エントロピー) 場合、
    # 全員一致でも「同じ誤答への集団確信」の疑いがある -> 格上を呼んで検証させる。
    # 経験的な閾値: 即答できる事実問題でも Scout は 7点台後半まで上がるため 8.0
    SCOUT_UNCERTAIN = 8.0

    def __init__(self, quiet=False, secret=False):
        from transformers import AutoTokenizer
        self.quiet = quiet
        self.tok = AutoTokenizer.from_pretrained(TOKENIZER)
        self.dict = JGenDict(DEFAULT_MODEL)
        # 同一プロセス内では 1 本の RustBrain を保持する。
        # 入口ルーティングは router_classifier.ClassifyOnlyBrain 経由のみ (Omni)。
        # deliberate / speak は別論理ハンドル (同一ウェイト・二重ロードなし)。
        # ClassifyOnlyBrain では speak しない。plan_steal / escalate はフォールバック残置。
        self.brain = RustBrain(DEFAULT_MODEL)
        self.deliberate_brain = self.brain   # R0 / encode / encode_soft
        self.speak_brain = self.brain        # generate のみ。ClassifyOnly 禁止
        from memory_guard import GUARD as _guard
        _guard.register_trimmable("jgen:router", self.brain.trim)
        self.axes = AxisAnchors()
        self.memory = CortexMemory(axes=self.axes)
        self.memory.enabled = not secret
        self.trace = ThoughtTrace()
        self.sem = self.dict.semantic_mask(self.tok)
        self._worker = None   # tier-1 エスカレーション (jgen)
        self._sage = None     # tier-2 エスカレーション (HF大型)
        self._bridges = []    # Ollama / LM Studio 参加者 (常時参加)
        self._participants = []  # (name, obj) 現在議論に参加中の外部モデル
        self.language = None  # 発話言語の強制 ("Japanese" / "English" / None=自動)
        self._forced_speaker = None  # (name, obj) 発話役の強制指定
        from router_reflex import RouterReflex
        from injection_policy import InjectionPolicy
        self.reflex = RouterReflex()  # ルーターの進化層 (経験→ステップ数削減)
        self.injections = InjectionPolicy()  # 注入レシピ学習 (どこに何を入れるか)
        self.demo = None  # DemoCouncilHook | None (デモモード時のみ)
        # Phase 5: 命題レキシコン (VERANTYX_CODEC=0 で無効化; 既定は学習済みなら有効)
        self.lexicon = None
        try:
            from concept_lexicon import ConceptLexicon, LEXICON_PATH, codec_enabled
            if codec_enabled() and os.path.exists(LEXICON_PATH):
                self.lexicon = ConceptLexicon(LEXICON_PATH)
                self.log(f"{C_SYS}  [Codec] ConceptLexicon loaded "
                         f"({len(self.lexicon.labels)} props, "
                         f"hold_acc={self.lexicon.hold_acc}){C_RESET}")
        except Exception:
            self.lexicon = None

    def lexicon_read(self, vec, top_k=3):
        """隠れ状態を命題レキシコンで英語ラベル化。未学習なら空。"""
        if not self.lexicon or not self.lexicon.available:
            return []
        return self.lexicon.read(vec, top_k=top_k)

    def lexicon_write_soft(self, label, alpha=0.85):
        """命題ラベル → soft 仮想トークン (評議会注入用)。未学習/未知ラベルなら None。"""
        if not self.lexicon or not self.lexicon.available:
            return None
        if label not in self.lexicon.labels:
            return None
        direction = self.lexicon.write(label, scale=10.0)
        dist = dist_from_vector(self.dict, self.tok, direction, self.sem, top_k=32)
        embed_rows = np.asarray(self.dict._embed_f16, dtype=np.float32)
        return dist_to_soft_numpy(dist, self.tok, embed_rows)

    def memorize_with_codec(self, text, kind="fact"):
        """永遠の記憶へ刻印し、レキシコン方向があれば codec_label/codec_dir も付与。"""
        mvec = embed_text(self.brain, self.tok, text)
        concepts = []
        try:
            from verantyx_mind import translate_vector
            concepts = translate_vector(self.dict, self.tok, mvec)
        except Exception:
            pass
        codec_label, codec_dir = None, None
        if self.lexicon and self.lexicon.available:
            pred, score = self.lexicon.nearest_label(mvec)
            if pred and score > 0.25:
                codec_label = pred
                codec_dir = self.lexicon.write(pred, scale=1.0)
        self.memory.add(
            mvec, text, concepts=concepts, kind=kind,
            codec_label=codec_label, codec_dir=codec_dir)
        return codec_label

    def add_bridge(self, spec):
        """外部LLMサーバー (ollama[:model] / lmstudio[:model]) を評議会に常時参加させる。"""
        from verantyx_bridges import make_participant
        p = make_participant(spec)
        self._bridges.append(p)
        self.log(f"{C_SYS}  [Bridge] {p.name} が評議会に参加{C_RESET}")
        return p

    def log(self, msg):
        if not self.quiet:
            print(msg)

    # ── エスカレーション梯子 ──
    def _rebuild_participants(self):
        parts = [(b.name, b) for b in self._bridges]
        if self._worker is not None:
            parts.append((self._worker.name, self._worker))
        if self._sage is not None:
            parts.append((self._sage.name, self._sage))
        self._participants = parts

    def _escalate(self, level, reason=""):
        """level 1: jgenワーカー / level 2: HF大型モデル (どちらも遅延ロード)。
        RAM が足りない時は HF 直ロードを避けて外部サーバー (Ollama/LM Studio) を
        身代わりの賢者として招集する (OOM クラッシュ防止)。"""
        from memory_guard import GUARD
        import verantyx_config
        ok = False
        worker_pref = verantyx_config.resolve_worker_pref()
        if level >= 1 and self._worker is None and worker_pref != "none":
            import jgen_forge
            joined = {b.name for b in self._bridges}
            cands = [m for m in jgen_forge.load_registry()["models"]
                     if m["status"] == "ready" and m["jgen"] != DEFAULT_MODEL
                     and m["name"] not in joined]
            if worker_pref != "auto":
                # 設定でワーカーを固定: レジストリ名 or .jgen パスで一致を探す
                pinned = [m for m in cands
                          if m["name"] == worker_pref or m["jgen"] == worker_pref]
                if pinned:
                    cands = pinned
                else:
                    self.log(f"{C_SYS}  [Config] worker '{worker_pref}' がレジストリに"
                             f"見つかりません。auto にフォールバック{C_RESET}")
            if cands and GUARD.can_load("jgen_worker", "jgenワーカー"):
                self.log(f"{C_SYS}  [Escalate{reason}] jgenワーカー '{cands[0]['name']}' を招集{C_RESET}")
                self._worker = JGenParticipant(cands[0])
                ok = True
        sage_dir = verantyx_config.resolve_sage_dir()  # False=禁止 / None=auto / パス
        if level >= 2 and self._sage is None:
            if sage_dir is False:
                ok = self._escalate_to_bridge(reason) or ok
            elif GUARD.ensure("hf_sage_9b", "HF Sage (大型モデル)"):
                self.log(f"{C_SYS}  [Escalate{reason}] 大型モデルをベクトル強奪モードで招集{C_RESET}")
                self._sage = HFSage(model_dir=sage_dir)
                GUARD.register_unloadable("hf_sage", 19.0, self._unload_sage)
                ok = True
            else:
                ok = self._escalate_to_bridge(reason)
        self._rebuild_participants()
        return ok

    def _unload_sage(self):
        if self._sage is not None:
            try:
                self._sage.close()
            except Exception:
                pass
            self._sage = None
            self._rebuild_participants()

    def _escalate_to_bridge(self, reason=""):
        """RAM 不足時の身代わり: 稼働中の外部LLMサーバーを賢者役として招集。"""
        if self._bridges:
            return False  # 既に参加済み
        try:
            from verantyx_bridges import detect_backends
            found = detect_backends()
            spec = "lmstudio" if found.get("lmstudio") else ("ollama" if found.get("ollama") else None)
            if spec:
                self.log(f"{C_MEM}  [Escalate{reason}] RAM不足のため外部サーバーを賢者役に招集{C_RESET}")
                self.add_bridge(spec)
                return True
        except Exception:
            pass
        self.log(f"{C_MEM}  [Escalate{reason}] RAM不足かつ外部サーバーなし。現有戦力で続行{C_RESET}")
        return False

    # ── ズレ注入 (摂動テスト) ──
    def _perturb_test(self, question, consensus, consensus_dist, role_toks, base_norm):
        """機械的なズレを意図的に起こし、評議会が修正できるかを試す。
        合意の対抗馬 (次点候補) を強めた偽の合意を全役割に注入し、
        それでも同じ答えに戻ってくるなら合意は頑健 (ズレを認識して修正できた)。
        流されて答えが変わるなら合意は脆く、議論を続けるべきシグナル。"""
        # 本当に意見の異なる対抗馬を選ぶ (合意と同語の別トークンはスキップ)
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
        lie = (0.4 * cn + 0.6 * rn)
        lie = lie / (np.linalg.norm(lie) + 1e-8) * base_norm
        e_lie = self.dict.to_embedding(lie, mask=self.sem)
        self.log(f"{C_SYS}  [ズレ注入] 対抗馬 '{rival[0].strip()}' を強めた偽合意を全役割に注入して耐性試験...{C_RESET}")
        test_vecs = []
        for name, _, _, _ in ROLES:
            z = self.brain.encode_soft(e_lie[None, :], role_toks[name])
            test_vecs.append(z / (np.linalg.norm(z) + 1e-8))
        test_consensus = np.mean(test_vecs, axis=0)
        test_consensus = test_consensus / (np.linalg.norm(test_consensus) + 1e-8) * base_norm
        drift = float((test_consensus / (np.linalg.norm(test_consensus) + 1e-8)) @ cn)
        test_top1 = dist_top1(dist_from_vector(self.dict, self.tok, test_consensus, self.sem))
        recovered = answers_agree(test_top1, dist_top1(consensus_dist))
        return recovered, drift, test_top1

    # ── 漁夫の利 (プラン強奪と再注入) ──
    def _plan_steal(self, question):
        """0.5B 自身は思考を深められない。そこで最強の参加者から
        『解き方のプラン』の分布だけを強奪し、ベクトルに変換して
        別のモデルたち (内部役割 + 次ラウンドの外部参加者) へしれっと注入する。
        受け取った側はプランに対して修正や反論を始める = 議論の誘発。"""
        donor = None
        if self._sage is not None:
            donor = (self._sage.name, self._sage)
        elif self._bridges:
            donor = (self._bridges[0].name, self._bridges[0])
        elif self._worker is not None:
            donor = (self._worker.name, self._worker)
        if donor is None:
            return None
        name, part = donor
        plan_q = ("What single concept, method, or first step is key to solving this? "
                  "Answer with one word.\n" + question)
        try:
            dist, _ = part.opine_dist(plan_q, None)
        except Exception:
            return None
        base = float(np.linalg.norm(self.brain.encode(
            self.tok.encode("plan", add_special_tokens=False)))) + 1e-8
        z_plan = dist_to_hidden(self.dict, self.tok, dist, base)
        if z_plan is None:
            return None
        cs = "  ".join(f"'{s.strip()}'({w*100:.0f}%)" for s, w in dist[:3])
        self.log(f"{C_MEM}  [漁夫の利] '{name}' からプランを強奪: {cs} → 全役割へ注入{C_RESET}")
        return z_plan

    # ── 議論本体 ──
    def deliberate(self, question, rounds="auto", escalation=True,
                   pre_escalate=0, rounds_cap=None, perturb_test=True,
                   injection_recipe=None):
        auto = (rounds == "auto")
        max_rounds = rounds_cap or (4 if auto else int(rounds))
        recipe = injection_recipe or "none"
        # 学習済みレシピ: 脆い問題は深く、早期プラン注入はラウンドを節約しない
        if recipe == "deep_rounds":
            max_rounds = max(max_rounds, 5)
            perturb_test = True
        # 反射弓: 過去の類似問題で必要だった階層を最初から招集 (ラウンドの節約)
        if pre_escalate and escalation:
            self._escalate(pre_escalate, reason=" 反射(類似問題の経験)")
        role_toks = {n: role_tokens(self.tok, d, question) for n, _, d, _ in ROLES}
        # 事前ロード済み (--sage やMCPの前回呼び出しで招集済み) の参加者はそのまま参加
        self._rebuild_participants()

        self.log(f"{C_SYS}  [Council] ラウンド0: 各役割が独立に思考 (実フォワード x{len(ROLES)})...{C_RESET}")
        # R0: 合意 soft なし・役割間非共有 (交差汚染なし)
        brain_d = self.deliberate_brain
        opinions = {n: brain_d.encode(role_toks[n]) for n, _, _, _ in ROLES}
        intent = opinions["Commander"].copy()
        intent_n = intent / (np.linalg.norm(intent) + 1e-8)
        base_norm = float(np.linalg.norm(intent)) + 1e-8

        # DivergencePacket (命題サイズ) — 独立 R0 から構築
        from divergence_packet import packet_from_hidden_dist, packets_to_serializable
        from divergence_exchange import (
            exchange_packets, weighted_consensus_vector, proposition_hint_text,
        )
        role_dists = {}
        divergence_packets = []
        for name, _, _, temp in ROLES:
            z = opinions[name]
            dist = dist_from_vector(self.dict, self.tok, z, self.sem)
            role_dists[name] = dist
            divergence_packets.append(packet_from_hidden_dist(
                name, z, dist, dictionary=self.dict, tok=self.tok))

        exchange = exchange_packets(
            divergence_packets,
            zs=opinions,
            dists=role_dists,
            reinfer_done=False,
        )
        self.log(f"{C_MEM}  [Divergence] div={exchange.divergence:.3f} "
                 f"action={exchange.action} S={exchange.trace_dict()['S_i']}{C_RESET}")

        # 乖離大 → 割れた役割だけ命題サイズ hint で再推論 1 回 (escalate off でも可)
        # soft はトークン列展開 + 短い probe。長い role_toks キャリアは内容を洗うので使わない。
        if exchange.action == "reinfer" and exchange.split_roles:
            hint = proposition_hint_text(divergence_packets, exchange.split_roles)
            try:
                e_rows = np.asarray(self.dict._embed_f16, dtype=np.float32)
                hint_ids = self.tok.encode(f"Reconcile: {hint}", add_special_tokens=False)[:32]
                hint_dist = []
                # hint トークンを擬似 dist にして sequence soft 化
                if hint_ids:
                    w = 1.0 / len(hint_ids)
                    for i in hint_ids:
                        hint_dist.append((self.tok.decode([int(i)]), w))
                for name in exchange.split_roles:
                    if name not in role_toks:
                        continue
                    old_dist = role_dists.get(name) or []
                    if hint_dist:
                        opinions[name] = encode_with_dist_soft(
                            brain_d, self.tok, e_rows, hint_dist,
                            probe="answer", max_soft=16)
                    else:
                        continue
                    new_dist = dist_from_vector(
                        self.dict, self.tok, opinions[name], self.sem)
                    # 候補質量保護: reinfer で正解候補が落ちたら旧 dist をブレンド
                    role_dists[name] = protect_dist_mass(old_dist, new_dist)
                    # z も保護後 dist から hidden 合成へ寄せる (同一モデル内)
                    try:
                        z_prot = dist_to_hidden(
                            self.dict, self.tok, role_dists[name], base_norm)
                        if z_prot is not None:
                            opinions[name] = z_prot
                    except Exception:
                        pass
                divergence_packets = []
                for name, _, _, _ in ROLES:
                    divergence_packets.append(packet_from_hidden_dist(
                        name, opinions[name], role_dists[name],
                        dictionary=self.dict, tok=self.tok))
                exchange = exchange_packets(
                    divergence_packets,
                    zs=opinions,
                    dists=role_dists,
                    reinfer_done=True,
                )
                self.log(f"{C_MEM}  [Divergence] after reinfer div={exchange.divergence:.3f} "
                         f"action={exchange.action} "
                         f"(dist-mass protected){C_RESET}")
            except Exception as e:
                self.log(f"{C_MEM}  [Divergence] reinfer soft failed: {e}{C_RESET}")

        # S_i 加重の仮合意 (多数決しない) — 以降のラウンドの種
        si_consensus = weighted_consensus_vector(
            opinions, exchange.weights, base_norm=base_norm)
        if si_consensus is not None:
            consensus = si_consensus
            consensus_dist = dist_from_vector(self.dict, self.tok, consensus, self.sem)
        else:
            consensus, consensus_dist = None, None

        self._last_divergence = exchange.trace_dict()
        self._last_divergence_packets = packets_to_serializable(divergence_packets)

        # ブリッジ (外部サーバー) は賢者の身代わりなので階層2として数える
        esc_level = (2 if (self._sage is not None or self._bridges)
                     else (1 if self._worker is not None else 0))
        trace_rounds = [{
            "round": 0,
            "phase": "divergence_r0",
            "divergence": exchange.trace_dict(),
            "action": exchange.action,
            "S_i": exchange.trace_dict().get("S_i"),
        }]
        prev_top1 = None
        perturb_done = plan_done = False
        z_plan = None
        self._last_fragile = False
        self._last_injection = recipe
        # early_steal: 意見割れを待たず、格上がいれば最初からプランを強奪して注入
        if recipe == "early_steal" and self._participants:
            z_plan = self._plan_steal(question)
            plan_done = z_plan is not None
            if z_plan is not None:
                self.log(f"{C_MEM}  [Injection] 学習済みレシピ early_steal を適用{C_RESET}")
        # 乖離がなお高く escalate 推奨 → 既存フォールバックへ (escalation off ならスキップ)
        if exchange.action == "escalate" and escalation and auto and esc_level < 2:
            if self._escalate(esc_level + 1, reason=" divergence_exchange"):
                esc_level += 1
        if (exchange.action == "escalate" and not plan_done and self._participants
                and recipe in ("none", "plan_steal")):
            plan_done = True
            z_plan = self._plan_steal(question)
            if z_plan is not None:
                self._last_injection = "plan_steal"
        for rnd in range(1, max_rounds + 1):
            if self.demo is not None:
                self.demo.on_round(rnd)
            vecs, weights, round_ops = [], [], []
            confident_top1 = []  # 確信を持った参加者の第一候補 (回答レベルの合意判定用)
            # S_i をラウンド1の初期加重にブレンド (非多数決)
            si_w = exchange.weights or {}
            for name, color, directive, temp in ROLES:
                z = opinions[name]
                zn = z / (np.linalg.norm(z) + 1e-8)
                _, entropy, p, top = self.dict.resonance(z, temperature=temp, mask=self.sem)
                cloud = token_cloud(self.tok, p, top, k=4)
                coherence = float(zn @ intent_n)
                w = max(coherence, 0.05) / (1.0 + entropy)
                if name in si_w:
                    w = 0.5 * w + 0.5 * float(si_w[name]) * (w + 0.1)
                vecs.append(zn); weights.append(w)
                if entropy < 4.0:
                    confident_top1.append(dist_top1(probs_to_dist(self.tok, p)))
                round_ops.append({"name": name, "entropy": round(float(entropy), 2),
                                  "top": [[s, round(float(pr), 3)] for s, pr in cloud],
                                  "vec_idx": self.trace.put_vector(z),
                                  "S_i": round(float(si_w.get(name, 0.0)), 4)})
                cs = "  ".join(f"'{s}'({pr*100:.0f}%)" for s, pr in cloud)
                self.log(f"{color}    {name:9s} | H={entropy:5.2f} bits | 整合={coherence:+.2f} | 発言: {cs}{C_RESET}")
                if self.demo is not None:
                    self.demo.on_opinion(name, float(entropy), cs)

            # 外部参加者 (jgenワーカー / HF大型): 語彙分布インターリンガで交信
            for pname, part in self._participants:
                t0 = time.time()
                try:
                    dist, inner = part.opine_dist(question, consensus_dist)
                except Exception as e:
                    self.log(f"{C_MEM}    {pname:9s} | 応答エラー: {e} (このラウンドは棄権){C_RESET}")
                    continue
                z_p = dist_to_hidden(self.dict, self.tok, dist, base_norm)
                if z_p is None:
                    self.log(f"{C_MEM}    {pname:9s} | 空応答 (このラウンドは棄権){C_RESET}")
                    continue
                zn = z_p / (np.linalg.norm(z_p) + 1e-8)
                h_p = dist_entropy(dist)
                seniority = 3.0 if part is self._sage else 1.5
                vecs.append(zn); weights.append(seniority / (1.0 + h_p))
                if h_p < 4.0:
                    confident_top1.append(dist_top1(dist))
                round_ops.append({"name": pname, "entropy": round(float(h_p), 2),
                                  "top": [[s.strip(), round(float(w), 3)] for s, w in dist[:4]],
                                  "vec_idx": self.trace.put_vector(z_p)})
                cs = "  ".join(f"'{s.strip()}'({w*100:.0f}%)" for s, w in dist[:4])
                self.log(f"{C_MEM}    {pname:9s} | H={h_p:5.2f} bits | ({time.time()-t0:.1f}s, hijack) | 発言: {cs}{C_RESET}")
                if self.demo is not None:
                    # 外部参加者は Worker-2 ペインに寄せて可視化
                    self.demo.on_opinion("Worker-2", float(h_p), f"{pname}: {cs}")
                    self.demo.on_transfer("Worker-2", "Commander", "dist")

            W = np.array(weights); W /= W.sum()
            consensus = sum(w * v for w, v in zip(W, vecs))
            consensus = consensus / (np.linalg.norm(consensus) + 1e-8) * base_norm
            # Phase 5: レキシコン方向で合意を軽くロック (学習済み・高類似時のみ)
            if self.lexicon and self.lexicon.available:
                hits = self.lexicon.read(consensus, top_k=1)
                if hits and hits[0][1] > 0.35:
                    try:
                        locked = self.lexicon.write(
                            consensus, [hits[0][0]], alpha=0.25, mode="add")
                        consensus = locked / (np.linalg.norm(locked) + 1e-8) * base_norm
                        self.log(f"{C_SYS}  [Codec] lexicon lock → {hits[0][0][:50]} "
                                 f"(cos={hits[0][1]:.2f}){C_RESET}")
                    except Exception:
                        pass
            consensus_dist = dist_from_vector(self.dict, self.tok, consensus, self.sem)
            consensus_top1 = dist_top1(consensus_dist)

            M = np.stack(vecs)
            agree_cos = float((M @ M.T)[np.triu_indices(len(vecs), 1)].mean())
            # 回答レベルの全会一致: 確信を持つ参加者全員の第一候補が合意と一致するか
            unanimous = bool(confident_top1) and all(
                answers_agree(t, consensus_top1) for t in confident_top1)
            _, c_entropy, p, top = self.dict.resonance(consensus, temperature=0.9, mask=self.sem)
            c_cloud = token_cloud(self.tok, p, top, k=4)
            cs = "  ".join(f"'{s}'({pr*100:.0f}%)" for s, pr in c_cloud)
            uni = "全会一致" if unanimous else "意見割れ"
            self.log(f"{C_THINK}  ── Round {rnd} 合意 | {uni} | cos {agree_cos:.3f} {bar(agree_cos)} | H={c_entropy:5.2f} | {cs}{C_RESET}")
            trace_rounds.append({"round": rnd, "agreement": round(float(agree_cos), 4),
                                 "unanimous": unanimous, "top1": consensus_top1,
                                 "entropy": round(float(c_entropy), 2),
                                 "opinions": round_ops,
                                 "consensus_vec_idx": self.trace.put_vector(consensus),
                                 "escalation_level": esc_level,
                                 "divergence_action": exchange.action})

            scout_h = [op["entropy"] for op in round_ops if op["name"].startswith("Scout")]
            scout_uncertain = bool(scout_h) and (sum(scout_h) / len(scout_h) > self.SCOUT_UNCERTAIN)
            # Scoutが答えをロックできない間は、全階層を招集し終えるまで収束と認めない
            converged = unanimous and not (scout_uncertain and escalation and auto and esc_level < 2)
            # 最上位まで招集済みなら、合意の第一候補が2ラウンド安定した時点で打ち切り
            stable = esc_level == 2 and prev_top1 is not None and consensus_top1 == prev_top1
            prev_top1 = consensus_top1
            if converged or stable:
                # 終了前に一度だけ、機械的なズレを起こして耐性を試す。
                # ズレを認識して元の合意へ修正できる = 頑健。流される = 脆い。
                if perturb_test and not perturb_done and rnd < max_rounds:
                    perturb_done = True
                    recovered, drift, lured = self._perturb_test(
                        question, consensus, consensus_dist, role_toks, base_norm)
                    trace_rounds[-1]["perturb"] = {
                        "recovered": recovered, "drift_cos": round(drift, 4),
                        "lured_to": lured}
                    if recovered:
                        self.log(f"{C_THINK}  >> ズレに耐えて合意へ復帰 (cos {drift:.2f})。"
                                 f"合意は頑健。議論終了。{C_RESET}")
                        break
                    self._last_fragile = True
                    self.log(f"{C_MEM}  >> ズレで合意が '{lured}' に崩れた (cos {drift:.2f})。"
                             f"脆い合意 → 修正のため議論続行{C_RESET}")
                else:
                    why = "意見が収束しました" if converged else "合意が安定しました"
                    self.log(f"{C_THINK}  >> {why}。議論終了。{C_RESET}")
                    break
            if rnd == max_rounds:
                break
            # auto モード: 意見が割れた、または「探索役が答えをロックできないのに
            # 全員一致」(集団確信バイアスの兆候) の時だけ格上を招集
            need_help = (not unanimous) or scout_uncertain or self._last_fragile
            if escalation and auto and need_help and esc_level < 2:
                reason = (f" Scout不確実H={sum(scout_h)/len(scout_h):.1f}" if scout_uncertain and unanimous
                          else (" 脆い合意" if self._last_fragile and unanimous else " 意見割れ"))
                if self._escalate(esc_level + 1, reason=reason):
                    esc_level += 1
            # 漁夫の利: 意見が割れて格上が参加している時、一度だけ最強参加者から
            # 「解き方のプラン」を強奪し、仮想トークンとして小型役割へ注入する。
            # 学習済みレシピ plan_steal なら、意見割れを待たず格上がいれば発動する。
            want_steal = (not unanimous) or (recipe == "plan_steal")
            if not plan_done and want_steal and self._participants:
                plan_done = True
                z_plan = self._plan_steal(question)
                if z_plan is not None:
                    self._last_injection = (
                        "plan_steal" if recipe in ("none", "plan_steal") else recipe)
                    if recipe == "plan_steal":
                        self.log(f"{C_MEM}  [Injection] 学習済みレシピ plan_steal を適用{C_RESET}")
                elif recipe == "plan_steal":
                    self._last_injection = "none"  # 強奪失敗 → 実際に使ったのは none

            # 合意は dist 列 soft + 短い answer probe (長い role_toks は洗ってしまう)
            e_rows = np.asarray(self.dict._embed_f16, dtype=np.float32)
            cdist = consensus_dist or dist_from_vector(
                self.dict, self.tok, consensus, self.sem)
            soft = dist_to_soft_sequence(cdist, self.tok, e_rows, max_soft=12)
            if z_plan is not None:
                e_plan = self.dict.to_embedding(z_plan, mask=self.sem)
                soft = np.vstack([e_plan[None, :], soft])
            self.log(f"{C_SYS}  [Council] Round {rnd+1}: 合意"
                     f"{'+強奪プラン' if z_plan is not None else ''}を仮想トークン列として注入...{C_RESET}")
            if self.demo is not None:
                self.demo.on_transfer("Commander", "Scout-A", "consensus")
                self.demo.on_transfer("Commander", "Scout-B", "consensus")
                self.demo.on_transfer("Commander", "Worker-1", "consensus")
                self.demo.on_transfer("Commander", "Worker-2", "consensus")
            probe = soft_probe_tokens(self.tok, "answer")
            for name, _, _, _ in ROLES:
                old_d = dist_from_vector(
                    self.dict, self.tok, opinions[name], self.sem)
                opinions[name] = brain_d.encode_soft(soft, probe)
                new_d = dist_from_vector(
                    self.dict, self.tok, opinions[name], self.sem)
                # ラウンド間でも候補質量を落とさない
                protected = protect_dist_mass(old_d, new_d, min_overlap=0.20)
                try:
                    z_prot = dist_to_hidden(
                        self.dict, self.tok, protected, base_norm)
                    if z_prot is not None:
                        opinions[name] = z_prot
                except Exception:
                    pass

        # 概念翻訳
        _, _, p, top = self.dict.resonance(consensus, temperature=1.0, mask=self.sem)
        concepts, seen = [], set()
        for s, _ in token_cloud(self.tok, p, top, k=24):
            key = s.strip().lower().lstrip("-_")
            if len(s) >= 2 and key not in seen and any(c.isalnum() or ord(c) > 0x2E80 for c in s):
                seen.add(key)
                concepts.append(s.strip())
            if len(concepts) >= 6:
                break
        # 異モデル境界用: 生 z ではなく語彙分布を保持 (speaker_bridge が使う)
        try:
            self._last_consensus_dist = dist_from_vector(
                self.dict, self.tok, consensus, self.sem)
        except Exception:
            self._last_consensus_dist = None
        self._last_consensus = consensus
        return consensus, concepts, trace_rounds, esc_level

    def _get_puzzle_worker(self, use_divergence=True):
        """company worker 用 Matryoshka を遅延共有 (同一ルーター脳)。"""
        holder = getattr(self, "_company_puzzle", None)
        want_div = bool(use_divergence)
        if holder is not None and getattr(holder, "_company_div", None) == want_div:
            return holder
        from verantyx_matryoshka import MatryoshkaCouncil
        holder = MatryoshkaCouncil(
            quiet=True,
            brain=self.brain,
            dictionary=self.dict,
            tok=self.tok,
            axes=getattr(self, "axes", None),
            carrier_alpha=0.08 if want_div else 0.0,
            enable_lexicon=want_div,
        )
        holder._company_div = want_div
        self._company_puzzle = holder
        return holder

    def deliberate_company(self, question, rounds=1, logic_force=None,
                           use_puzzle_worker=True, puzzle_depth=2):
        """会社型ベクトル合議: ceo/worker/critic/integrator → AbstractCanvas → LinkChannel。

        use_puzzle_worker=True: worker を 6軸パズル (deliberate-only) に差し替え。
        自然言語の chair 要約は使わない。境界は dist / canvas のみ。
        """
        from abstract_link import AbstractCanvas, LinkChannel
        from speaker_bridge import classify_task_kind

        brain_d = self.deliberate_brain
        e_rows = np.asarray(self.dict._embed_f16, dtype=np.float32)
        kind = classify_task_kind(question)
        is_logic = bool(logic_force) if logic_force is not None else _looks_like_logic(question)
        n_rounds = max(1, int(rounds) if rounds != "auto" else (2 if is_logic else 1))
        # puzzle worker 時は重いので company ラウンドは既定1 (logic でも)
        if use_puzzle_worker and rounds == "auto":
            n_rounds = 1

        self.log(f"{C_SYS}  [Company] ベクトル会社型熟議 "
                 f"(roles={len(COMPANY_ROLES)} rounds={n_rounds} "
                 f"logic={is_logic} puzzle_worker={use_puzzle_worker}){C_RESET}")

        role_toks = {
            n: role_tokens(self.tok, d, question) for n, _, d, _ in COMPANY_ROLES
        }
        canvases = []
        opinions = {}
        role_dists = {}
        puzzle_meta = None
        for name, color, _directive, temp in COMPANY_ROLES:
            props = []
            if name == "ceo":
                props.append("Decompose task and lock the answer target.")
            elif name == "worker":
                props.append("Compute the working answer carefully.")
            elif name == "critic":
                props.append("Find contradictions; propose rival answers.")
                if is_logic:
                    props.append("Check arithmetic and logical consistency.")
            elif name == "integrator":
                props.append("Merge into one coherent final answer.")

            # worker = puzzle (発話なし・軸接合の dist だけもらう)
            if name == "worker" and use_puzzle_worker:
                try:
                    puzzle = self._get_puzzle_worker(use_divergence=True)
                    prec = puzzle.ask(
                        question, depth=int(puzzle_depth), gate=0.15,
                        use_divergence=True, speak=False)
                    dist = sharpen_dist(prec.get("consensus_dist") or [])
                    z = prec.get("consensus_z")
                    if z is None and dist:
                        z = dist_to_hidden(self.dict, self.tok, dist, 10.0)
                    if z is None:
                        z = brain_d.encode(role_toks[name])
                        dist = sharpen_dist(dist_from_vector(
                            self.dict, self.tok, z, self.sem, temperature=temp))
                    props.append(
                        "Puzzle axes joined: "
                        + ",".join(prec.get("joined_axes") or [])[:120])
                    puzzle_meta = {
                        "joined_axes": prec.get("joined_axes"),
                        "dropped_axes": prec.get("dropped_axes"),
                        "axis_energies": prec.get("axis_energies"),
                        "elapsed_s": prec.get("elapsed_s"),
                    }
                    self.log(
                        f"{color}    worker     | puzzle joined="
                        f"{prec.get('joined_axes')} "
                        f"top={[t for t, _ in (dist or [])[:4]]}{C_RESET}")
                except Exception as e:
                    self.log(f"{C_MEM}  [Company] puzzle worker failed: {e} "
                             f"— fallback encode{C_RESET}")
                    z = brain_d.encode(role_toks[name])
                    dist = sharpen_dist(dist_from_vector(
                        self.dict, self.tok, z, self.sem, temperature=temp))
            else:
                z = brain_d.encode(role_toks[name])
                dist = sharpen_dist(dist_from_vector(
                    self.dict, self.tok, z, self.sem, temperature=temp))
                self.log(f"{color}    {name:11s} | top={[t for t, _ in dist[:4]]}{C_RESET}")

            opinions[name] = z
            role_dists[name] = dist
            concepts = [t.strip() for t, _ in dist[:6] if t and t.strip()]
            sig = None
            if self.axes is not None and getattr(self.axes, "available", False):
                try:
                    sig = self.axes.signature(z).tolist()
                except Exception:
                    sig = None
            meta = {"role": name, "task_kind": kind, "logic": is_logic}
            if name == "worker" and puzzle_meta:
                meta["puzzle"] = puzzle_meta
            canvases.append(AbstractCanvas(
                question=question,
                axis_sig=sig,
                dist=dist,
                concepts=concepts,
                propositions=props,
                confidence=float(dist[0][1]) if dist else 0.4,
                source=f"role:{name}",
                meta=meta,
            ))

        link = LinkChannel(
            memory=self.memory, axes=self.axes,
            dictionary=self.dict, tok=self.tok, log=self.log)

        # フラクタル十字: 役割 canvas を同型ノードとして並べ→包む
        cross_root = None
        try:
            from matryoshka_cross import company_roles_to_cross
            cross_root = company_roles_to_cross(
                canvases, question=question, wrap_roles=True)
            self._last_cross = cross_root
            self.log(
                f"{C_SYS}  [Cross] arrange→wrap scale={cross_root.scale} "
                f"id={cross_root.id} children={len(cross_root.children)} "
                f"top={[t for t, _ in (cross_root.dist or [])[:3]]}{C_RESET}")
        except Exception as e:
            self._last_cross = None
            self.log(f"{C_SYS}  [Cross] build skipped: {e}{C_RESET}")

        blended = None
        trace_rounds = []
        for rnd in range(n_rounds):
            matched = [link.pattern_match(c) for c in canvases]
            blended = link.puzzle_join(matched)
            # 包んだ親十字の dist 質量を合流に混ぜて潰しを抑える
            if cross_root is not None and cross_root.dist:
                blended.dist = protect_dist_mass(
                    cross_root.dist, blended.dist or [],
                    min_overlap=0.18, blend=0.40)
                if cross_root.axis_sig is not None and blended.axis_sig is None:
                    blended.axis_sig = list(cross_root.axis_sig)
            critic = next((c for c in matched if str(c.source).endswith("critic")), None)
            if critic and critic.dist:
                blended.dist = protect_dist_mass(
                    critic.dist, blended.dist, min_overlap=0.15, blend=0.35)
            if is_logic or kind in ("tool", "ambiguous"):
                try:
                    from puzzle_decontaminator import PuzzleDecontaminator
                    deco = PuzzleDecontaminator()
                    blended, report = deco.purify(blended, aggressive=is_logic)
                    self.log(
                        f"{C_SYS}  [Company] decontam contam="
                        f"{report.contamination_score:.2f} "
                        f"purity+={report.purity_gain:.2f}{C_RESET}")
                except Exception as e:
                    self.log(f"{C_SYS}  [Company] decontam skip: {e}{C_RESET}")
            blended.source = "company"
            blended.meta["round"] = rnd
            blended.meta["medium"] = "vector_company"
            if cross_root is not None:
                blended.meta["cross"] = {
                    "id": cross_root.id,
                    "scale": cross_root.scale,
                    "n_children": len(cross_root.children),
                    "op": (cross_root.meta or {}).get("op"),
                }
            if rnd + 1 < n_rounds and blended.dist:
                soft = dist_to_soft_sequence(
                    blended.dist, self.tok, e_rows, max_soft=12)
                probe = soft_probe_tokens(self.tok, "answer")
                base_z = opinions.get("integrator")
                if base_z is None:
                    base_z = opinions.get("worker")
                base_norm = float(np.linalg.norm(
                    soft[0] if base_z is None else base_z)) + 1e-8
                new_canvases = []
                for c in canvases:
                    name = (c.meta or {}).get("role") or str(c.source).replace("role:", "")
                    old_d = role_dists.get(name) or c.dist
                    z_new = brain_d.encode_soft(soft, probe)
                    new_d = protect_dist_mass(
                        old_d,
                        sharpen_dist(dist_from_vector(
                            self.dict, self.tok, z_new, self.sem)),
                        min_overlap=0.20)
                    try:
                        z_prot = dist_to_hidden(
                            self.dict, self.tok, new_d, base_norm)
                        if z_prot is not None:
                            z_new = z_prot
                    except Exception:
                        pass
                    opinions[name] = z_new
                    role_dists[name] = new_d
                    nc = c.clone()
                    nc.dist = new_d
                    nc.concepts = [t.strip() for t, _ in new_d[:6] if t and t.strip()]
                    new_canvases.append(nc)
                canvases = new_canvases
            trace_rounds.append({
                "round": rnd,
                "medium": "vector_company",
                "roles": [c.source for c in matched],
                "top_dist": [(s, round(w, 4)) for s, w in (blended.dist or [])[:6]],
                "decontam": (blended.meta or {}).get("decontam"),
            })

        z_int = opinions.get("integrator")
        if z_int is None:
            z_int = opinions.get("worker")
        if z_int is None and blended is not None and blended.dist:
            z_int = dist_to_hidden(self.dict, self.tok, blended.dist, 10.0)
        consensus = z_int
        concepts = list((blended.concepts if blended is not None else []) or [])[:6]
        if not concepts and blended is not None and blended.dist:
            concepts = [t.strip() for t, _ in blended.dist[:6] if t and t.strip()]

        self._last_consensus = consensus
        self._last_consensus_dist = list(
            (blended.dist if blended is not None else []) or [])
        self._last_abstract_canvas = blended
        self._last_divergence = {
            "medium": "vector_company",
            "logic": is_logic,
            "n_rounds": n_rounds,
            "puzzle_worker": bool(use_puzzle_worker),
            "puzzle": puzzle_meta,
            "cross": (cross_root.as_dict() if cross_root is not None else None),
        }
        if blended is not None:
            blended.meta["puzzle_worker"] = bool(use_puzzle_worker)
            if puzzle_meta:
                blended.meta["puzzle"] = puzzle_meta
        # 記憶用: 包みノードを MemoryGraph 正本候補に
        if cross_root is not None and self.memory.enabled:
            try:
                mg = cross_root.to_memory_graph(
                    l3_text=f"Q: {question[:120]}", kind="matryoshka_cross")
                self._last_cross_graph = mg
            except Exception:
                self._last_cross_graph = None
        esc_level = (2 if (self._sage is not None or self._bridges)
                     else (1 if self._worker is not None else 0))
        return consensus, concepts, trace_rounds, esc_level

    # ── 発話 ──
    def router_answer(self, question, max_new="auto"):
        """評議会なし: ルーター (0.5B) が直接生成。ベンチマークのベースライン用。"""
        small = resolve_tokens(max_new, small=True)
        sys_p = "You are a helpful assistant."
        if self.language:
            native = {"Japanese": "常に日本語で答えてください。",
                      "Chinese": "请始终用中文回答。",
                      "Korean": "항상 한국어로 대답하세요。"}
            sys_p += " Respond only in " + self.language + ". " + native.get(self.language, "")
        pr = (f"<|im_start|>system\n{sys_p}<|im_end|>\n"
              f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n")
        out = self.speak_brain.generate(self.tok.encode(pr, add_special_tokens=False), small)
        return polish_answer(self.tok.decode(out, skip_special_tokens=True).strip())

    def speak(self, question, concepts, esc_level, max_new="auto",
              force_router_speaker=False, brief=None):
        """max_new='auto' がスマートモード: 固定上限で切らず、EOS で自然に
        終わらせる (上限は暴走防止の天井のみ)。天井到達時は文境界で整える。
        force_router_speaker=True のとき、言語指定でもワーカーを招集せず
        常駐ルーターだけが発話する (ベンチの公平比較用)。
        ClassifyOnlyBrain では speak しない (公理: 分身禁止)。
        brief: SpeakerBrief (異モデル境界用。生 z は渡さない)。"""
        from router_classifier import ClassifyOnlyBrain
        from speaker_bridge import SpeakerBrief, remember_hits_for_question
        if isinstance(self.speak_brain, ClassifyOnlyBrain):
            raise RuntimeError(
                "Council.speak: speak_brain must not be ClassifyOnlyBrain")
        if brief is None:
            mem = remember_hits_for_question(
                self.memory, self.brain, self.tok, question, k=3)
            brief = SpeakerBrief.build(
                question,
                concepts=concepts,
                consensus_dist=getattr(self, "_last_consensus_dist", None),
                memory_hits=mem,
                language=self.language,
            )
        self._last_speaker_brief = brief.as_dict()
        # 外部speaker向けは質問末尾、ルーター(0.5B)向けはsystem側に言語指示を置く
        q_ext = (f"{question}\n(Respond in {self.language}.)"
                 if self.language else question)
        big = resolve_tokens(max_new, small=False)
        small = resolve_tokens(max_new, small=True)

        def _call_speak(obj, q, n):
            try:
                return obj.speak(q, concepts, n, brief=brief)
            except TypeError:
                return obj.speak(q, concepts, n)

        if self._forced_speaker is not None and not force_router_speaker:
            name, obj = self._forced_speaker
            is_small = isinstance(obj, JGenParticipant)
            self.log(f"\n{C_SPEAK}━━ [Speaker] '{name}' が合意を発話 (指定speaker) "
                     f"| brief={brief.task_kind} ━━{C_RESET}")
            text = polish_answer(_call_speak(obj, q_ext, small if is_small else big))
            self.log(f"{C_SPEAK}  🤖 {text}{C_RESET}")
            return text, name
        # 言語強制時: 0.5Bルーターは言語指示に従えないので、jgenワーカーを
        # 発話役として遅延招集する (qwen2.5 は多言語指示に追従できる)。
        # 公平ベンチ (force_router_speaker) ではこの招集を行わない。
        if (not force_router_speaker and self.language
                and self._sage is None and self._worker is None and not self._bridges):
            self._escalate(1, reason=" 言語指定発話")
        # 話者選択は「強いモデル優先」: sage > bridge(外部大型) > worker(0.5B) > router。
        # 議論に参加した最強モデルに発話させる (0.5Bワーカーは複雑な回答を作れず
        # トークン天井で途切れるため、格上がいるなら必ず譲る)。
        use_router = force_router_speaker
        if not use_router and esc_level >= 2 and self._sage is not None:
            name, fn = self._sage.name, lambda: _call_speak(self._sage, q_ext, big)
        elif not use_router and self._bridges:
            bridge = self._bridges[-1]  # 最後に招集された賢者役 (最有力)
            name, fn = bridge.name, lambda: _call_speak(bridge, q_ext, big)
        elif not use_router and self._worker is not None and (esc_level >= 1 or self.language):
            name, fn = self._worker.name, lambda: _call_speak(self._worker, q_ext, small)
        else:
            def _router_speak():
                # 発話役専用ブリーフ (system のみ)。生ベクトルは渡さない。
                sys_p = brief.system_prompt(for_api=False)
                pr = (f"<|im_start|>system\n{sys_p}<|im_end|>\n"
                      f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n")
                out = self.speak_brain.generate(
                    self.tok.encode(pr, add_special_tokens=False), small)
                return self.tok.decode(out, skip_special_tokens=True).strip()
            name, fn = "router", _router_speak
        self.log(f"\n{C_SPEAK}━━ [Speaker] '{name}' が合意を発話 "
                 f"| brief={brief.task_kind} ━━{C_RESET}")
        text = polish_answer(fn())
        self.log(f"{C_SPEAK}  🤖 {text}{C_RESET}")
        return text, name

    # ── ワンショット: 議論 + 発話 + 記憶 + 軌跡 ──
    def ask(self, question, rounds="auto", escalation=True, speak_tokens="auto",
            memorize=True, perturb_test=True, force_router_speaker=False,
            medium="company", use_puzzle_worker=True, separate_speaker=False,
            puzzle_depth=2):
        """medium:
          company — 会社型ベクトル合議 (デフォルト; AbstractCanvas + LinkChannel)
          council — 旧 ROLES soft 評議会
          (NL 対照は ask_nl)
        use_puzzle_worker: company の worker を 6軸パズルにする
        separate_speaker: 実験 — Speak を speak_locked (再推論禁止) に縛る
        """
        t0 = time.time()
        from verantyx_mind import embed_text
        # 公平比較: ワーカーが既に載っていれば外し、議論もルーター脳のみにする
        if force_router_speaker and self._worker is not None:
            try:
                self._worker.close()
            except Exception:
                pass
            self._worker = None
            self._rebuild_participants()
        qvec = embed_text(self.brain, self.tok, question)
        # 反射弓: 類似問題の経験があればステップを省く (secret 中は不使用)
        pre_esc, rounds_cap = 0, None
        injection_recipe = None
        use_company = str(medium or "company").lower() in (
            "company", "vector_company", "swarm")
        if self.memory.enabled and not use_company:
            advice = self.reflex.advise(qvec)
            if advice:
                pre_esc = advice["pre_escalate"]
                rounds_cap = advice["max_rounds"]
                self.log(f"{C_SYS}  [Reflex] 類似経験が発火 (sim {advice['sim']:.2f} "
                         f"'{advice['src']}...') → 階層{pre_esc}を事前招集"
                         f"{f' / 上限{rounds_cap}ラウンド' if rounds_cap else ''}"
                         f"{' / 過去に脆かった問題' if advice['fragile'] else ''}{C_RESET}")
                if advice["fragile"]:
                    rounds_cap = None  # 脆かった問題は深く議論させる
                    injection_recipe = "deep_rounds"  # 脆さの記憶 → 深い議論レシピ
            # 注入レシピの想起: 「この種の問題ではここに注入すると良かった」
            inj = self.injections.advise(qvec)
            if inj:
                injection_recipe = inj["recipe"]
                self.log(f"{C_SYS}  [Injection] 学習済みレシピ発火 (sim {inj['sim']:.2f} "
                         f"'{inj['src']}...') → {injection_recipe} "
                         f"(✓{inj['successes']}/✗{inj['failures']}){C_RESET}")
        if use_company:
            consensus, concepts, trace_rounds, esc_level = self.deliberate_company(
                question, rounds=rounds, use_puzzle_worker=use_puzzle_worker,
                puzzle_depth=puzzle_depth)
        else:
            consensus, concepts, trace_rounds, esc_level = self.deliberate(
                question, rounds=rounds, escalation=escalation,
                pre_escalate=pre_esc, rounds_cap=rounds_cap,
                perturb_test=perturb_test, injection_recipe=injection_recipe)
        # TriLanguageHinge: GraphLang.step + 往復忠実度 (立体十字ヒンジ)
        brief = None
        hinge = None
        fidelity_blob = None
        try:
            from abstract_link import canvas_from_council, gather_web_snippets
            from speaker_bridge import (
                remember_hits_for_question, classify_task_kind,
            )
            from language_runtime import build_hinge_for_council
            seed = getattr(self, "_last_abstract_canvas", None)
            if seed is None or not hasattr(seed, "dist"):
                seed = canvas_from_council(
                    question,
                    consensus_z=consensus,
                    consensus_dist=getattr(self, "_last_consensus_dist", None),
                    concepts=concepts,
                    axes=self.axes,
                    packets=getattr(self, "_last_divergence_packets", None),
                )
            # logic: integrator 前 decontam をもう一度 (GraphLang 入口)
            if _looks_like_logic(question) and seed is not None:
                try:
                    from puzzle_decontaminator import PuzzleDecontaminator
                    seed, _rep = PuzzleDecontaminator().purify(seed, aggressive=True)
                except Exception:
                    pass
            peers = list(self._bridges or [])
            if self._sage is not None:
                peers.append(self._sage)
            if self._worker is not None and not force_router_speaker:
                peers.append(self._worker)
            hinge = build_hinge_for_council(
                self, peers=peers, force_router_speaker=force_router_speaker)
            refined, fid_reports = hinge.run_graph_step_with_fidelity(
                seed,
                consensus_z=consensus,
                consensus_dist=getattr(self, "_last_consensus_dist", None),
                graph_rounds=1,
            )
            self._last_abstract_canvas = refined
            self._last_hinge = hinge
            kind = classify_task_kind(question)
            mem = remember_hits_for_question(
                self.memory, self.brain, self.tok, question, k=3)
            web = gather_web_snippets(question, k=3) if kind == "factual" else []
            peer_texts = [refined.as_peer_summary()]
            if refined.pattern_hits:
                peer_texts.extend(refined.pattern_hits[:2])
            speak_purpose = "speak_locked" if separate_speaker else "speak"
            brief = refined.to_speaker_brief(
                memory_texts=mem, web_texts=web, peer_texts=peer_texts,
                language=self.language, purpose=speak_purpose)
            if separate_speaker:
                self.log(f"{C_SPEAK}  [Speaker] experimental speak_locked "
                         f"lock={brief.locked_answer!r}{C_RESET}")
            fidelity_blob = hinge.fidelity_summary()
            scores = " ".join(
                f"{r.direction.split('(')[0]}={r.score:.2f}" for r in fid_reports)
            deco = (refined.meta or {}).get("decontam") or {}
            resteps = (refined.meta or {}).get("resteps", 0)
            self.log(f"{C_SYS}  [GraphLang] step+fidelity {scores} "
                     f"ok={fidelity_blob.get('all_ok')} "
                     f"hits={len(refined.pattern_hits)} kind={kind}{C_RESET}")
            if deco:
                self.log(
                    f"{C_SYS}  [PuzzleDecontam] contam={deco.get('contamination_score')} "
                    f"purity+={deco.get('purity_gain')} "
                    f"dropped_cand={deco.get('dropped_candidates')} "
                    f"resteps={resteps} actions={deco.get('actions')}{C_RESET}")
        except Exception as e:
            self.log(f"{C_SYS}  [GraphLang] skipped: {e}{C_RESET}")
            brief = None
        # GraphLang 失敗時でも separate_speaker ならロック発話を組む
        if brief is None and separate_speaker:
            from speaker_bridge import SpeakerBrief, remember_hits_for_question
            mem = remember_hits_for_question(
                self.memory, self.brain, self.tok, question, k=3)
            brief = SpeakerBrief.build(
                question, concepts=concepts,
                consensus_dist=getattr(self, "_last_consensus_dist", None),
                memory_hits=mem, language=self.language,
                purpose="speak_locked")
        answer, speaker = self.speak(question, concepts, esc_level, max_new=speak_tokens,
                                     force_router_speaker=force_router_speaker,
                                     brief=brief)
        if separate_speaker and speaker == "router":
            speaker = "router(speak_locked)"
        # 発話後: nl↔graph 忠実度
        if hinge is not None and getattr(self, "_last_abstract_canvas", None) is not None:
            try:
                nl_rep = hinge.measure_nl_roundtrip(
                    question, answer or "", self._last_abstract_canvas)
                fidelity_blob = hinge.fidelity_summary()
                self.log(f"{C_SYS}  [NaturalLang] fidelity "
                         f"{nl_rep.direction}={nl_rep.score:.2f} "
                         f"mean={fidelity_blob.get('mean_score', 0):.2f}{C_RESET}")
            except Exception as e:
                self.log(f"{C_SYS}  [NaturalLang] fidelity skipped: {e}{C_RESET}")
        if self.demo is not None and answer:
            self.demo.on_answer(answer)

        trace_id = uuid.uuid4().hex[:12]
        used_recipe = getattr(self, "_last_injection", injection_recipe or "none")
        # 実際にプラン注入が走ったかでレシピを補正
        if used_recipe == "none" and any(
                r.get("perturb") for r in trace_rounds):
            pass
        record = {
            "trace_id": trace_id, "ts": time.time(), "question": question,
            "answer": answer, "speaker": speaker, "concepts": concepts,
            "escalation_level": esc_level, "elapsed_s": round(time.time() - t0, 1),
            "rounds": trace_rounds,
            "medium": (
                "vector_company_puzzle" if (
                    use_company and use_puzzle_worker) else (
                    "vector_company" if use_company else "vector_council")),
            "use_puzzle_worker": bool(use_puzzle_worker) if use_company else False,
            "separate_speaker": bool(separate_speaker),
            "injection_recipe": used_recipe,
            "divergence_packets": getattr(self, "_last_divergence_packets", []),
            "divergence": getattr(self, "_last_divergence", None),
            "speaker_brief": getattr(self, "_last_speaker_brief", None),
            "abstract_link": (
                getattr(self, "_last_abstract_canvas", None).meta
                if getattr(self, "_last_abstract_canvas", None) is not None
                and hasattr(self._last_abstract_canvas, "meta")
                else getattr(self, "_last_abstract_canvas", None)
            ),
            "fidelity": fidelity_blob,
            "decontam": (
                (getattr(self, "_last_abstract_canvas", None).meta or {}).get("decontam")
                if getattr(self, "_last_abstract_canvas", None) is not None
                and hasattr(self._last_abstract_canvas, "meta")
                else None
            ),
        }
        if self.memory.enabled:
            self.trace.save(record)
        else:
            self.log(f"{C_SYS}  [Secret] 軌跡も記憶も永続化しません{C_RESET}")
        if memorize and self.memory.enabled:
            # Phase 5: attach proposition label + codec direction when lexicon exists.
            codec_label, codec_dir = None, None
            if self.lexicon and self.lexicon.available:
                hits = self.lexicon.read(consensus, top_k=1)
                if hits and hits[0][1] > 0.12:
                    codec_label = hits[0][0]
                    codec_dir = self.lexicon.direction(codec_label)
            # 異種共通の記憶言語 (MemoryGraph) を正本として併記
            mem_graph = None
            try:
                from memory_graph import MemoryGraph
                label = f"Q: {question}  →  A: {answer}"
                # フラクタル十字ノードがあれば正本にする
                cg = getattr(self, "_last_cross_graph", None)
                if cg is not None:
                    mem_graph = cg
                    mem_graph.l3_text = label
                else:
                    canvas = getattr(self, "_last_abstract_canvas", None)
                    if canvas is not None and hasattr(canvas, "axis_sig"):
                        mem_graph = MemoryGraph.from_canvas(
                            canvas, l3_text=label, kind="council")
                    else:
                        sig = None
                        if self.axes and self.axes.available and consensus is not None:
                            sig = self.axes.signature(consensus).tolist()
                        mem_graph = MemoryGraph.from_axis_sig(
                            sig, concepts=concepts,
                            candidates=getattr(self, "_last_consensus_dist", None) or [],
                            l3_text=label, kind="council")
            except Exception:
                mem_graph = None
            self.memory.add(
                consensus, f"Q: {question}  →  A: {answer}",
                concepts=concepts, kind="council",
                codec_label=codec_label, codec_dir=codec_dir,
                graph=mem_graph,
                propositions=(mem_graph.propositions if mem_graph else None),
                candidates=(mem_graph.candidates if mem_graph else
                            getattr(self, "_last_consensus_dist", None)),
                extra={"trace_id": trace_id})
            fragile = getattr(self, "_last_fragile", False)
            # ルーターの進化: この問題に要した階層/ラウンド/脆さを反射として刻印
            self.reflex.record(qvec, question, intent="chat", esc_level=esc_level,
                               rounds=len(trace_rounds),
                               fragile=fragile,
                               elapsed_s=record["elapsed_s"], brain=self.brain)
            # 注入レシピの学習: 脆くなければ成功、脆ければ失敗として刻印
            # (ユーザーフィードバックがあれば後から reinforce で上書きされる)
            self.injections.record(
                qvec, question, recipe=used_recipe,
                success=not fragile, fragile=fragile, brain=self.brain,
                meta={"esc_level": esc_level, "rounds": len(trace_rounds),
                      "trace_id": trace_id})
            self._last_qvec = qvec
            self._last_injection_id = None
            # 直近の注入ノード id を保持 (フィードバック強化用)
            if self.injections.index:
                self._last_injection_id = self.injections.index[-1]["id"]
        self.log(f"{C_THINK}  [Council] 完了 ({record['elapsed_s']}s) | trace={trace_id} "
                 f"| 注入={used_recipe} | 概念: {concepts}{C_RESET}")
        return record

    def _nl_generate(self, system, user, max_new=96):
        """同一ルーター脳での短いテキスト生成 (NL評議会用)。"""
        n = resolve_tokens(max_new, small=True)
        n = min(n, int(max_new) if isinstance(max_new, int) else 96)
        if self.language:
            native = {"Japanese": "常に日本語で答えてください。",
                      "Chinese": "请始终用中文回答。",
                      "Korean": "항상 한국어로 대답하세요。"}
            system = (system + " Respond only in " + self.language + ". "
                      + native.get(self.language, ""))
        pr = (f"<|im_start|>system\n{system}<|im_end|>\n"
              f"<|im_start|>user\n{user}<|im_end|>\n"
              f"<|im_start|>assistant\n")
        out = self.brain.generate(self.tok.encode(pr, add_special_tokens=False), n)
        return self.tok.decode(out, skip_special_tokens=True).strip()

    def ask_nl(self, question, rounds=2, speak_tokens=128):
        """自然言語で役割が意見交換する評議会 (ベクトル熟議の対照実験)。

        同じルーター脳・同じ役割指示を使い、媒体だけテキストにする。
        戻り値の形は ask() に揃える (answer/speaker/rounds/elapsed_s)。
        """
        t0 = time.time()
        max_rounds = max(1, int(rounds) if rounds != "auto" else 2)
        gen_calls = 0
        char_budget = 0
        consensus_text = ""
        trace_rounds = []
        self.log(f"{C_SYS}  [NL-Council] 自然言語熟議開始 "
                 f"({max_rounds} rounds × {len(ROLES)} roles){C_RESET}")

        for rnd in range(1, max_rounds + 1):
            opinions = []
            round_ops = []
            for name, color, directive, _temp in ROLES:
                ctx = ""
                if consensus_text:
                    ctx = (f"\n\nPrevious council consensus:\n{consensus_text}\n"
                           f"Revise or defend your view briefly.")
                user = f"{question}{ctx}\n\nGive a short opinion (1-3 sentences). End with your best answer."
                try:
                    text = self._nl_generate(directive, user, max_new=80)
                except Exception as e:
                    text = f"(error: {e})"
                gen_calls += 1
                char_budget += len(text)
                opinions.append((name, text))
                round_ops.append({"name": name, "text": text[:240]})
                self.log(f"{color}    {name:9s} | {text[:100]}{C_RESET}")

            # テキスト合意: Commander が全意見を要約して答えを決める
            joined = "\n".join(f"- {n}: {t}" for n, t in opinions)
            synth_sys = ("You are the council chair. Read all role opinions and "
                         "state the single best final answer clearly.")
            synth_user = (f"Question: {question}\n\nOpinions:\n{joined}\n\n"
                          f"Consensus answer:")
            try:
                consensus_text = self._nl_generate(synth_sys, synth_user, max_new=100)
            except Exception as e:
                consensus_text = opinions[0][1] if opinions else ""
                self.log(f"{C_MEM}  [NL-Council] 合意生成失敗: {e}{C_RESET}")
            gen_calls += 1
            char_budget += len(consensus_text)
            self.log(f"{C_THINK}  ── NL Round {rnd} 合意 | {consensus_text[:120]}{C_RESET}")
            trace_rounds.append({
                "round": rnd, "medium": "natural_language",
                "opinions": round_ops,
                "consensus_text": consensus_text[:500],
            })

        answer = polish_answer(consensus_text)
        # 最終発話を明示的にもう一度 (ask と同じ「発話」段階)
        try:
            final = self._nl_generate(
                "You are a helpful assistant. Answer concisely.",
                f"Question: {question}\nCouncil consensus: {consensus_text}\n\nFinal answer:",
                max_new=speak_tokens if isinstance(speak_tokens, int) else 128)
            gen_calls += 1
            char_budget += len(final)
            if final.strip():
                answer = polish_answer(final)
        except Exception:
            pass

        record = {
            "trace_id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "question": question,
            "answer": answer,
            "speaker": "router",
            "concepts": [],
            "escalation_level": 0,
            "elapsed_s": round(time.time() - t0, 1),
            "rounds": trace_rounds,
            "medium": "natural_language",
            "gen_calls": gen_calls,
            "char_budget": char_budget,
            "injection_recipe": "none",
        }
        self.log(f"{C_THINK}  [NL-Council] 完了 ({record['elapsed_s']}s) | "
                 f"gen_calls={gen_calls} chars≈{char_budget}{C_RESET}")
        return record

    def memory_search(self, query, k=3):
        """永遠の記憶の検索 (MCP用)。"""
        from verantyx_mind import embed_text
        qv = embed_text(self.brain, self.tok, query)
        hits = self.memory.search(qv, k=k, query_text=query)
        out = []
        for text, score, _vec, concepts, idx in hits:
            rec = self.memory.index[idx]
            out.append({"id": idx, "text": text, "score": round(score, 3),
                        "concepts": concepts, "trace_id": rec.get("trace_id")})
        return out

    def close(self):
        self.brain.close()
        if self._worker is not None:
            self._worker.close()


# ── 軌跡の再生 ────────────────────────────────────────────────────────────────
def replay_trace(trace_id):
    """保存された思考の軌跡をベクトルのまま再共鳴させて辿る。"""
    from transformers import AutoTokenizer
    trace = ThoughtTrace()
    rec = trace.load(trace_id)
    if rec is None:
        print(f"trace '{trace_id}' が見つかりません")
        return None
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    dictionary = JGenDict(DEFAULT_MODEL)
    axes = AxisAnchors()
    sem = dictionary.semantic_mask(tok)

    print(f"{C_SYS}━━ 思考の軌跡 {rec['trace_id']} ━━{C_RESET}")
    print(f"{C_SYS}  Q: {rec['question']}{C_RESET}")
    print(f"{C_SYS}  A: {rec['answer']} (speaker: {rec['speaker']}, {rec['elapsed_s']}s, esc={rec['escalation_level']}){C_RESET}")
    for r in rec["rounds"]:
        uni = "全会一致" if r.get("unanimous") else "意見割れ"
        print(f"{C_THINK}  ── Round {r['round']} | {uni} | cos {r['agreement']:.3f} | H={r['entropy']:.2f} | esc_lv{r['escalation_level']}{C_RESET}")
        for op in r["opinions"]:
            tops = "  ".join(f"'{s}'({w*100:.0f}%)" for s, w in op["top"])
            print(f"    {op['name']:9s} | H={op['entropy']:5.2f} | {tops}")
        # 合意ベクトルを再共鳴 (保存されたベクトルそのものから思考を復元)
        z = trace.get_vector(r["consensus_vec_idx"])
        _, _, p, top = dictionary.resonance(z, temperature=0.9, mask=sem)
        cloud = token_cloud(tok, p, top, k=6)
        cs = "  ".join(f"'{s}'({pr*100:.0f}%)" for s, pr in cloud)
        line = f"    合意ベクトル再共鳴: {cs}"
        if axes.available:
            sig = axes.signature(z)
            dom = int(np.argmax(np.abs(sig)))
            line += f" | dominant axis: {AXIS_NAMES[dom].strip()}"
        print(f"{C_MEM}{line}{C_RESET}")
    return rec


def main():
    ap = argparse.ArgumentParser(description="ベクトル評議会オーケストレーター")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--rounds", default="auto", help="auto (収束/エスカレーション自動) または固定回数 N")
    ap.add_argument("--sage", action="store_true", help="最初から大型モデルを参加させる")
    ap.add_argument("--no-escalate", action="store_true", help="エスカレーション無効")
    ap.add_argument("--bridge", action="append", default=[],
                    help="外部LLMを参加させる: ollama[:model] / lmstudio[:model] (複数可)")
    ap.add_argument("--speak-tokens", default="auto",
                    help="auto (EOSで自然終了、途切れは文境界で整形) または固定 N")
    ap.add_argument("--no-memorize", action="store_true")
    ap.add_argument("--secret", action="store_true", help="記憶の参照/刻印なし (シークレット)")
    ap.add_argument("--traces", action="store_true", help="思考の軌跡一覧")
    ap.add_argument("--trace", default=None, help="軌跡IDを再生")
    args = ap.parse_args()

    if args.traces:
        for rec in ThoughtTrace().list():
            print(f"{rec['trace_id']}  {time.strftime('%m/%d %H:%M', time.localtime(rec['ts']))}  "
                  f"esc={rec['escalation_level']}  {rec['question'][:50]}  ->  {rec['answer'][:40]}")
        return
    if args.trace:
        replay_trace(args.trace)
        return
    if not args.prompt:
        print("--prompt / --traces / --trace のいずれかを指定してください")
        return

    print(f"{C_SYS}╔═══════════════════════════════════════════════╗")
    print(f"║  Verantyx Council — Latent Deliberation        ║")
    print(f"╚═══════════════════════════════════════════════╝{C_RESET}")
    council = Council(secret=args.secret)
    try:
        if args.sage:
            council._sage = HFSage()
        for spec in args.bridge:
            council.add_bridge(spec)
        council.ask(args.prompt, rounds=args.rounds,
                    escalation=not args.no_escalate,
                    speak_tokens=args.speak_tokens,
                    memorize=not args.no_memorize and not args.secret)
    finally:
        council.close()


if __name__ == "__main__":
    main()
