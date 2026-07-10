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
    DEFAULT_MODEL, TOKENIZER, HIDDEN, MEMORY_DIR,
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


# ── 語彙分布インターリンガ (異モデル間のベクトル交信路) ─────────────────────────
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


def dist_to_soft_numpy(dist, tok, embed_rows):
    """語彙分布 -> このモデルの埋め込み空間上の仮想トークン (numpy版)。"""
    acc = None; wsum = 0.0; nsum = 0.0
    for s, w in dist:
        ids = tok.encode(s, add_special_tokens=False)
        if not ids:
            continue
        rows = embed_rows[ids].astype(np.float32)
        r = rows.mean(axis=0)
        acc = w * r if acc is None else acc + w * r
        nsum += w * float(np.linalg.norm(rows, axis=1).mean())
        wsum += w
    e = acc / (wsum + 1e-8)
    e *= (nsum / (wsum + 1e-8)) / (np.linalg.norm(e) + 1e-8)
    return e.astype(np.float32)


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

    def speak(self, question, concepts, max_new=48):
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
        print(f"{C_SYS}  [Sage] {name} をロード中 (MPS/fp16)...{C_RESET}")
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_dir, dtype=torch.float16, low_cpu_mem_usage=True,
            attn_implementation="eager").to("mps").eval()
        self.embed_w = self.model.get_input_embeddings().weight
        self._embed_rows = None
        self.think_budget = think_budget
        self.first_special = min(self.tok.vocab_size, self.model.config.vocab_size
                                 if hasattr(self.model.config, "vocab_size") else 10**9)

    def _prompt_embeds(self, question, consensus_dist):
        torch = self.torch
        msgs = [{"role": "user", "content": question}]
        text = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        ids = self.tok(text, return_tensors="pt").input_ids.to("mps")
        e_ids = self.model.get_input_embeddings()(ids)
        if consensus_dist is not None:
            if self._embed_rows is None:
                self._embed_rows = self.embed_w.detach().float().cpu().numpy()
            e_soft = dist_to_soft_numpy(consensus_dist, self.tok, self._embed_rows)
            e_soft = torch.tensor(e_soft, dtype=torch.float16, device="mps").view(1, 1, -1)
            e_ids = torch.cat([e_soft, e_ids], dim=1)
        return e_ids

    def opine_dist(self, question, consensus_dist=None):
        """ベクトル強奪: 合意分布を注入した1フォワードで回答分布を抜き取る。"""
        torch = self.torch
        with torch.no_grad():
            e = self._prompt_embeds(question, consensus_dist)
            inner = ""
            if self.think_budget > 0:
                mask = torch.ones(e.shape[:2], dtype=torch.long, device="mps")
                gen = self.model.generate(
                    inputs_embeds=e, attention_mask=mask,
                    max_new_tokens=self.think_budget, do_sample=False,
                    pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
                inner = self.tok.decode(gen[0], skip_special_tokens=True)
                e = torch.cat([e, self.model.get_input_embeddings()(gen)], dim=1)
            cue = self.tok("\nThe answer is", return_tensors="pt").input_ids.to("mps")
            e2 = torch.cat([e, self.model.get_input_embeddings()(cue)], dim=1)
            mask2 = torch.ones(e2.shape[:2], dtype=torch.long, device="mps")
            o = self.model(inputs_embeds=e2, attention_mask=mask2)
            lg = o.logits[0, -1].float().cpu().numpy()
        lg[self.first_special:] = -np.inf
        lg -= lg[np.isfinite(lg)].max()
        p = np.exp(lg); p /= p.sum()
        top = np.argsort(p)[::-1][:48]
        dist = [(self.tok.decode([int(i)]), float(p[i])) for i in top if p[i] > 1e-5]
        s = sum(w for _, w in dist)
        return [(t, w / s) for t, w in dist], inner

    def speak(self, question, concepts, max_new=60):
        torch = self.torch
        sys_p = "Answer concisely."
        if concepts:
            sys_p += " Council consensus concepts: " + ", ".join(concepts) + "."
        msgs = [{"role": "system", "content": sys_p},
                {"role": "user", "content": question}]
        text = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        enc = self.tok(text, return_tensors="pt").to("mps")
        with torch.no_grad():
            out = self.model.generate(**enc, max_new_tokens=max(max_new, 220), do_sample=False,
                                      pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
            cue = self.tok("\n\nFinal answer:", return_tensors="pt").input_ids.to("mps")
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
        with open(TRACE_VEC, "ab") as f:
            f.write(np.asarray(v, dtype=np.float16).reshape(HIDDEN).tobytes())
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
        self.brain = RustBrain(DEFAULT_MODEL)
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
        self.reflex = RouterReflex()  # ルーターの進化層 (経験→ステップ数削減)

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
                   pre_escalate=0, rounds_cap=None):
        auto = (rounds == "auto")
        max_rounds = rounds_cap or (4 if auto else int(rounds))
        # 反射弓: 過去の類似問題で必要だった階層を最初から招集 (ラウンドの節約)
        if pre_escalate and escalation:
            self._escalate(pre_escalate, reason=" 反射(類似問題の経験)")
        role_toks = {n: role_tokens(self.tok, d, question) for n, _, d, _ in ROLES}
        # 事前ロード済み (--sage やMCPの前回呼び出しで招集済み) の参加者はそのまま参加
        self._rebuild_participants()

        self.log(f"{C_SYS}  [Council] ラウンド0: 各役割が独立に思考 (実フォワード x{len(ROLES)})...{C_RESET}")
        opinions = {n: self.brain.encode(role_toks[n]) for n, _, _, _ in ROLES}
        intent = opinions["Commander"].copy()
        intent_n = intent / (np.linalg.norm(intent) + 1e-8)
        base_norm = float(np.linalg.norm(intent)) + 1e-8

        consensus, consensus_dist = None, None
        # ブリッジ (外部サーバー) は賢者の身代わりなので階層2として数える
        esc_level = (2 if (self._sage is not None or self._bridges)
                     else (1 if self._worker is not None else 0))
        trace_rounds = []
        prev_top1 = None
        perturb_done = plan_done = False
        z_plan = None
        self._last_fragile = False
        for rnd in range(1, max_rounds + 1):
            vecs, weights, round_ops = [], [], []
            confident_top1 = []  # 確信を持った参加者の第一候補 (回答レベルの合意判定用)
            for name, color, directive, temp in ROLES:
                z = opinions[name]
                zn = z / (np.linalg.norm(z) + 1e-8)
                _, entropy, p, top = self.dict.resonance(z, temperature=temp, mask=self.sem)
                cloud = token_cloud(self.tok, p, top, k=4)
                coherence = float(zn @ intent_n)
                w = max(coherence, 0.05) / (1.0 + entropy)
                vecs.append(zn); weights.append(w)
                if entropy < 4.0:
                    confident_top1.append(dist_top1(probs_to_dist(self.tok, p)))
                round_ops.append({"name": name, "entropy": round(float(entropy), 2),
                                  "top": [[s, round(float(pr), 3)] for s, pr in cloud],
                                  "vec_idx": self.trace.put_vector(z)})
                cs = "  ".join(f"'{s}'({pr*100:.0f}%)" for s, pr in cloud)
                self.log(f"{color}    {name:9s} | H={entropy:5.2f} bits | 整合={coherence:+.2f} | 発言: {cs}{C_RESET}")

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

            W = np.array(weights); W /= W.sum()
            consensus = sum(w * v for w, v in zip(W, vecs))
            consensus = consensus / (np.linalg.norm(consensus) + 1e-8) * base_norm
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
                                 "escalation_level": esc_level})

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
                if auto and not perturb_done and rnd < max_rounds:
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
            # 「解き方のプラン」を強奪し、仮想トークンとして小型役割へ注入する
            if not plan_done and not unanimous and self._participants:
                plan_done = True
                z_plan = self._plan_steal(question)

            e_consensus = self.dict.to_embedding(consensus, mask=self.sem)
            soft = e_consensus[None, :]
            if z_plan is not None:
                e_plan = self.dict.to_embedding(z_plan, mask=self.sem)
                soft = np.stack([e_plan, e_consensus])
            self.log(f"{C_SYS}  [Council] Round {rnd+1}: 合意"
                     f"{'+強奪プラン' if z_plan is not None else ''}を仮想トークンとして全役割へ注入...{C_RESET}")
            for name, _, _, _ in ROLES:
                opinions[name] = self.brain.encode_soft(soft, role_toks[name])

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
        return consensus, concepts, trace_rounds, esc_level

    # ── 発話 ──
    def speak(self, question, concepts, esc_level, max_new="auto"):
        """max_new='auto' がスマートモード: 固定上限で切らず、EOS で自然に
        終わらせる (上限は暴走防止の天井のみ)。天井到達時は文境界で整える。"""
        # 外部speaker向けは質問末尾、ルーター(0.5B)向けはsystem側に言語指示を置く
        q_ext = (f"{question}\n(Respond in {self.language}.)"
                 if self.language else question)
        big = resolve_tokens(max_new, small=False)
        small = resolve_tokens(max_new, small=True)
        if self._forced_speaker is not None:
            name, obj = self._forced_speaker
            is_small = isinstance(obj, JGenParticipant)
            self.log(f"\n{C_SPEAK}━━ [Speaker] '{name}' が合意を発話 (指定speaker) ━━{C_RESET}")
            text = polish_answer(obj.speak(q_ext, concepts, small if is_small else big))
            self.log(f"{C_SPEAK}  🤖 {text}{C_RESET}")
            return text, name
        # 言語強制時: 0.5Bルーターは言語指示に従えないので、jgenワーカーを
        # 発話役として遅延招集する (qwen2.5 は多言語指示に追従できる)
        if self.language and self._sage is None and self._worker is None and not self._bridges:
            self._escalate(1, reason=" 言語指定発話")
        # 話者選択は「強いモデル優先」: sage > bridge(外部大型) > worker(0.5B) > router。
        # 議論に参加した最強モデルに発話させる (0.5Bワーカーは複雑な回答を作れず
        # トークン天井で途切れるため、格上がいるなら必ず譲る)。
        if esc_level >= 2 and self._sage is not None:
            name, fn = self._sage.name, lambda: self._sage.speak(q_ext, concepts, big)
        elif self._bridges:
            bridge = self._bridges[-1]  # 最後に招集された賢者役 (最有力)
            name, fn = bridge.name, lambda: bridge.speak(q_ext, concepts, big)
        elif self._worker is not None and (esc_level >= 1 or self.language):
            name, fn = self._worker.name, lambda: self._worker.speak(q_ext, concepts, small)
        else:
            def _router_speak():
                # 0.5Bはユーザー文中のメタ指示をオウム返ししがちなので system 側のみに置く
                sys_p = "You are a helpful assistant."
                if self.language:
                    native = {"Japanese": "常に日本語で答えてください。",
                              "Chinese": "请始终用中文回答。",
                              "Korean": "항상 한국어로 대답하세요。"}
                    sys_p += " Respond only in " + self.language + ". " + native.get(self.language, "")
                if concepts:
                    sys_p += " Council consensus concepts: " + ", ".join(concepts) + "."
                pr = (f"<|im_start|>system\n{sys_p}<|im_end|>\n"
                      f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n")
                out = self.brain.generate(self.tok.encode(pr, add_special_tokens=False), small)
                return self.tok.decode(out, skip_special_tokens=True).strip()
            name, fn = "router", _router_speak
        self.log(f"\n{C_SPEAK}━━ [Speaker] '{name}' が合意を発話 ━━{C_RESET}")
        text = polish_answer(fn())
        self.log(f"{C_SPEAK}  🤖 {text}{C_RESET}")
        return text, name

    # ── ワンショット: 議論 + 発話 + 記憶 + 軌跡 ──
    def ask(self, question, rounds="auto", escalation=True, speak_tokens="auto", memorize=True):
        t0 = time.time()
        from verantyx_mind import embed_text
        qvec = embed_text(self.brain, self.tok, question)
        # 反射弓: 類似問題の経験があればステップを省く (secret 中は不使用)
        pre_esc, rounds_cap = 0, None
        if self.memory.enabled:
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
        consensus, concepts, trace_rounds, esc_level = self.deliberate(
            question, rounds=rounds, escalation=escalation,
            pre_escalate=pre_esc, rounds_cap=rounds_cap)
        answer, speaker = self.speak(question, concepts, esc_level, max_new=speak_tokens)

        trace_id = uuid.uuid4().hex[:12]
        record = {
            "trace_id": trace_id, "ts": time.time(), "question": question,
            "answer": answer, "speaker": speaker, "concepts": concepts,
            "escalation_level": esc_level, "elapsed_s": round(time.time() - t0, 1),
            "rounds": trace_rounds,
        }
        if self.memory.enabled:
            self.trace.save(record)
        else:
            self.log(f"{C_SYS}  [Secret] 軌跡も記憶も永続化しません{C_RESET}")
        if memorize and self.memory.enabled:
            self.memory.add(consensus, f"Q: {question}  →  A: {answer}",
                            concepts=concepts, kind="council",
                            extra={"trace_id": trace_id})
            # ルーターの進化: この問題に要した階層/ラウンド/脆さを反射として刻印
            self.reflex.record(qvec, question, intent="chat", esc_level=esc_level,
                               rounds=len(trace_rounds),
                               fragile=getattr(self, "_last_fragile", False),
                               elapsed_s=record["elapsed_s"])
        self.log(f"{C_THINK}  [Council] 完了 ({record['elapsed_s']}s) | trace={trace_id} | 概念: {concepts}{C_RESET}")
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
