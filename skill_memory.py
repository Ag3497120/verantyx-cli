"""
skill_memory.py — スキル学習層 (フィードバック→予行演習→自己進化)
==============================================================================
認知アンカー (不変の土台) の上で、ユーザーとの対話から「やり方」を獲得して
進化していく層。RouterReflex が『どのルートを選ぶか』の反射なのに対し、
これは『どういう手順(ツールの組み合わせ)で解くか』の手続き記憶を貯める。

進化のループ:
  1. 獲得 (learn): ユーザーの修正フィードバック
       「私はこれを要求したのに。ツールAとBを使えば効率的では?」
     を捉え、対象タスク種別 + 提案された手順を『候補スキル』として抽出する。
  2. 予行演習 (rehearse): ユーザーのペルソナに対して擬似シミュレーションを回す。
     実行はせず「このペルソナのユーザーはこの手順の結果に満足するか」を
     頭脳モデルに採点させる (0-1)。安全な予行演習。
  3. 昇格 (promote): 演習スコアが閾値を超えたら proven に昇格し、次回から
     同種タスクでこの手順をルーターが最初から提案する。
  4. 強化: 実運用で使われて成功するたび score/hits を上げる。失敗で下げる。

スキルは問題ベクトルをキーに永続化され、類似タスクで想起される。
"""

import json
import os
import time

import numpy as np

CHRONO = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono")
SKILL_VEC = os.path.join(CHRONO, "skills.vectors")
SKILL_IDX = os.path.join(CHRONO, "skills.index.jsonl")
DIM = 1024
SIM_RECALL = 0.82       # これ以上似たタスクでスキルを想起
PROMOTE_SCORE = 0.6     # 予行演習でこのスコアを超えたら proven に昇格


class SkillLibrary:
    def __init__(self):
        os.makedirs(CHRONO, exist_ok=True)
        self.index = []
        if os.path.exists(SKILL_IDX):
            with open(SKILL_IDX) as f:
                self.index = [json.loads(l) for l in f if l.strip()]
        self._vecs = None

    def _vectors(self):
        if self._vecs is None and os.path.exists(SKILL_VEC):
            self._vecs = np.fromfile(SKILL_VEC, dtype=np.float32).reshape(-1, DIM)
        return self._vecs if self._vecs is not None else np.zeros((0, DIM), np.float32)

    # ── 想起 ──
    def recall(self, qvec, k=3, proven_only=False):
        V = self._vectors()
        if len(V) == 0:
            return []
        qn = np.asarray(qvec, dtype=np.float32)
        qn = qn / (np.linalg.norm(qn) + 1e-8)
        sims = V @ qn
        order = np.argsort(sims)[::-1]
        out = []
        for i in order:
            if sims[i] < SIM_RECALL:
                break
            node = self.index[i]
            if proven_only and node.get("status") != "proven":
                continue
            out.append((node, float(sims[i])))
            if len(out) >= k:
                break
        return out

    def best_plan(self, qvec):
        """類似タスクで最も信頼できる proven スキルの手順を返す (無ければ None)。"""
        hits = self.recall(qvec, k=3, proven_only=True)
        if not hits:
            return None
        node, sim = max(hits, key=lambda h: h[0].get("score", 0) * h[1])
        return {"plan": node["plan"], "sim": sim, "score": node.get("score", 0),
                "id": node["id"], "task_kind": node.get("task_kind", "")}

    # ── 獲得 ──
    def learn(self, qvec, task_kind, plan, source="user_feedback", status="proposed"):
        node = {
            "id": len(self.index), "ts": time.time(),
            "task_kind": task_kind[:120], "plan": plan[:500],
            "source": source, "status": status,
            "score": 0.0, "hits": 0, "rehearsal": None,
        }
        v = np.asarray(qvec, dtype=np.float32)
        v = v / (np.linalg.norm(v) + 1e-8)
        with open(SKILL_VEC, "ab") as f:
            v.tofile(f)
        with open(SKILL_IDX, "a") as f:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")
        self.index.append(node)
        self._vecs = None
        return node

    # ── 予行演習 (ペルソナ擬似シミュレーション) ──
    def rehearse(self, node, task_kind, persona, backend):
        """実行はせず、ペルソナ視点でこの手順の満足度を頭脳に採点させる。
        戻り値 score(0-1) と講評。閾値超なら呼び出し側が promote する。"""
        persona_desc = (", ".join(f"{n}" for n, _ in persona) if persona
                        else "(ペルソナ情報なし)")
        sim_prompt = [
            {"role": "system", "content":
             "You are a strict evaluator running a dry-run simulation. Given a user "
             "persona, a task type, and a proposed tool-plan, predict whether THIS user "
             "would be satisfied. Reply on the FIRST line exactly 'SCORE: <0.0-1.0>' "
             "then one short sentence why."},
            {"role": "user", "content":
             f"User persona (dominant interests): {persona_desc}\n"
             f"Task type: {task_kind}\n"
             f"Proposed tool-plan: {node['plan']}\n\n"
             "Would this plan efficiently satisfy this user? Score it."},
        ]
        try:
            out = backend.complete(sim_prompt, max_tokens=280).strip()
        except Exception as e:
            return 0.0, f"(rehearsal failed: {e})"
        score = _parse_score(out)
        node["rehearsal"] = {"score": score, "note": out[:200], "ts": time.time()}
        self._flush()
        return score, out

    def promote(self, node):
        node["status"] = "proven"
        node["score"] = max(node.get("score", 0.0), PROMOTE_SCORE)
        self._flush()

    def reinforce(self, node_id, success=True):
        for n in self.index:
            if n["id"] == node_id:
                n["hits"] = n.get("hits", 0) + 1
                n["score"] = float(np.clip(n.get("score", 0.0) + (0.1 if success else -0.15),
                                           0.0, 1.0))
                if n["score"] < 0.2:
                    n["status"] = "demoted"
                break
        self._flush()

    def _flush(self):
        with open(SKILL_IDX, "w") as f:
            for n in self.index:
                f.write(json.dumps(n, ensure_ascii=False) + "\n")

    def stats(self):
        by = {}
        for n in self.index:
            by[n.get("status", "?")] = by.get(n.get("status", "?"), 0) + 1
        return {"skills": len(self.index), "by_status": by,
                "hits": sum(n.get("hits", 0) for n in self.index)}


def _parse_score(text):
    import re
    # 1) 明示 SCORE: (thinking後に出ることもあるので最後の一致を採る)
    ms = re.findall(r"SCORE:?\s*([01](?:\.\d+)?|\.\d+)", text, re.IGNORECASE)
    if ms:
        try:
            return float(np.clip(float(ms[-1]), 0.0, 1.0))
        except ValueError:
            pass
    # 2) 'X/10' や百分率
    m = re.search(r"\b([0-9]{1,2})\s*/\s*10\b", text)
    if m:
        return float(np.clip(int(m.group(1)) / 10.0, 0.0, 1.0))
    m = re.search(r"\b([0-9]{1,3})\s*%", text)
    if m:
        return float(np.clip(int(m.group(1)) / 100.0, 0.0, 1.0))
    # 3) 素の 0.x 表記 (最後の一致)
    ms = re.findall(r"\b(0\.\d+|1\.0+)\b", text)
    if ms:
        return float(np.clip(float(ms[-1]), 0.0, 1.0))
    # 4) フォールバック: 肯定/否定語のヒューリスティック
    low = text.lower()
    neg = any(w in low for w in ("no", "not ", "wouldn", "inefficient", "不満", "非効率", "無駄"))
    pos = any(w in low for w in ("yes", "satisf", "efficient", "good", "満足", "効率的"))
    if pos and not neg:
        return 0.65
    if neg and not pos:
        return 0.25
    return 0.4


# ── フィードバック検知 (ユーザー発話が『修正提案』かを見分ける) ────────────────
_FEEDBACK_CUES = (
    "これを要求していたのに", "これを求めていたのに", "じゃなくて", "ではなくて",
    "使えば", "使ったら", "した方が", "すればいいのに", "すれば効率", "の方が効率",
    "もっと", "本当はこう", "こうしてほしかった", "こうすべき", "why didn't you",
    "you should have", "instead of", "would be more efficient", "could have used",
    "next time", "次回は", "次からは",
)
_TOOL_WORDS = ("web", "検索", "search", "fetch", "ファイル", "file", "shell",
               "シェル", "アプリ", "app", "クリック", "click", "スクショ", "screen",
               "ツール", "tool", "メモリ", "memory", "lexicon", "辞書")


def looks_like_feedback(text):
    """直前ターンへの修正フィードバックらしさを判定する。
    修正の合図 + ツール/やり方への言及が両方あれば True。"""
    has_cue = any(c in text for c in _FEEDBACK_CUES)
    mentions_method = any(w in text or w in text.lower() for w in _TOOL_WORDS)
    return has_cue and mentions_method


if __name__ == "__main__":
    lib = SkillLibrary()
    print("[Skill]", lib.stats())
    print("feedback? '検索とfetchを使えば効率的では':",
          looks_like_feedback("検索とfetchを使えば効率的では"))
    print("feedback? 'ありがとう':", looks_like_feedback("ありがとう"))
