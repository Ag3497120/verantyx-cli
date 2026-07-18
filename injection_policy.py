"""
injection_policy.py — ルーターの「注入レシピ」学習層
==============================================================================
哲学 (ユーザー構想):
  評議会の結論の質を上げるのは、ルーターを大きくすることではない。
  jgen などベクトル介入可能なモデルに対して、「どこに・何を・いつ注入すると
  結果が良くなるか」を日々覚えることで、0.5B ルーター自身が進化する。

  学習の主体は必ず vector_intervention=True の脳 (JGENルーター) の埋め込み。
  API モデルの表現では刻印しない。

レシピの種類 (離散アクション — 重み更新ではない):
  none          注入なし (合意ベクトルのみ回す)
  plan_steal    漁夫の利: 格上からプラン分布を強奪して早期注入
  early_steal   意見割れを待たず、最初のラウンドからプラン注入
  deep_rounds   脆い問題向け: ラウンド上限を緩め、摂動を必ず試す

成果信号:
  fragile=False / perturb recovered / ユーザー肯定フィードバック → 強化
  fragile=True / ユーザー否定 → 弱化・別レシピへ切替候補
"""

import json
import os
import time

import numpy as np

from verantyx_mind import fit_vec

CHRONO = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono")
INJ_VEC = os.path.join(CHRONO, "injection.vectors")
INJ_IDX = os.path.join(CHRONO, "injection.index.jsonl")
DIM = 1024
SIM_FIRE = 0.84

# 離散レシピ。ルーターが「選ぶ」対象。
RECIPES = ("none", "plan_steal", "early_steal", "deep_rounds")


class InjectionPolicy:
    def __init__(self):
        os.makedirs(CHRONO, exist_ok=True)
        self.index = []
        if os.path.exists(INJ_IDX):
            with open(INJ_IDX) as f:
                self.index = [json.loads(l) for l in f if l.strip()]
        self._vecs = None

    def _vectors(self):
        if self._vecs is None and os.path.exists(INJ_VEC):
            raw = np.fromfile(INJ_VEC, dtype=np.float32)
            n = (raw.size // DIM) * DIM
            if n == 0:
                self._vecs = np.zeros((0, DIM), np.float32)
            else:
                self._vecs = raw[:n].reshape(-1, DIM)
        return self._vecs if self._vecs is not None else np.zeros((0, DIM), np.float32)

    def fire(self, qvec, k=5):
        V = self._vectors()
        if len(V) == 0:
            return []
        qn = fit_vec(qvec, DIM)
        qn = qn / (np.linalg.norm(qn) + 1e-8)
        sims = V @ qn
        order = np.argsort(sims)[::-1][:k]
        return [(self.index[i], float(sims[i])) for i in order if sims[i] >= SIM_FIRE]

    def advise(self, qvec):
        """類似問題で成功した注入レシピを返す。無ければ None。
        返り値: {recipe, strength, sim, src, successes, failures}
        """
        hits = self.fire(qvec)
        if not hits:
            return None
        # 成功が多いレシピを優先。失敗が多いものは避ける。
        scored = []
        for node, sim in hits:
            ok = node.get("successes", 0)
            ng = node.get("failures", 0)
            score = sim + 0.05 * ok - 0.08 * ng
            if ng > ok + 1:
                continue  # 明らかに失敗続きのレシピは採用しない
            scored.append((score, node, sim))
        if not scored:
            return None
        _, node, sim = max(scored, key=lambda x: x[0])
        return {
            "recipe": node.get("recipe", "none"),
            "strength": float(node.get("strength", 1.0)),
            "sim": sim,
            "src": node.get("question", "")[:40],
            "successes": node.get("successes", 0),
            "failures": node.get("failures", 0),
            "id": node["id"],
        }

    def record(self, qvec, question, recipe, strength=1.0, success=True,
               fragile=False, brain=None, meta=None):
        """注入結果を刻印。vector_intervention 可能な脳のみ。"""
        if not getattr(brain, "vector_intervention", False):
            return None
        if recipe not in RECIPES:
            recipe = "none"
        # 同一レシピ・高類似の既存ノードがあれば強化/弱化だけする
        hits = self.fire(qvec, k=3)
        for node, sim in hits:
            if node.get("recipe") == recipe and sim >= 0.92:
                if success and not fragile:
                    node["successes"] = node.get("successes", 0) + 1
                else:
                    node["failures"] = node.get("failures", 0) + 1
                node["last_ts"] = time.time()
                self._flush()
                return node

        node = {
            "id": len(self.index),
            "ts": time.time(),
            "question": question[:160],
            "recipe": recipe,
            "strength": float(strength),
            "successes": 1 if (success and not fragile) else 0,
            "failures": 0 if (success and not fragile) else 1,
            "fragile": bool(fragile),
            "meta": meta or {},
        }
        v = fit_vec(qvec, DIM)
        v = v / (np.linalg.norm(v) + 1e-8)
        with open(INJ_VEC, "ab") as f:
            v.astype(np.float32).tofile(f)
        with open(INJ_IDX, "a") as f:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")
        self.index.append(node)
        self._vecs = None
        return node

    def reinforce(self, node_id, success=True):
        for n in self.index:
            if n["id"] == node_id:
                if success:
                    n["successes"] = n.get("successes", 0) + 1
                else:
                    n["failures"] = n.get("failures", 0) + 1
                n["last_ts"] = time.time()
                break
        self._flush()

    def _flush(self):
        with open(INJ_IDX, "w") as f:
            for n in self.index:
                f.write(json.dumps(n, ensure_ascii=False) + "\n")

    def summary(self, n=8):
        ranked = sorted(self.index,
                        key=lambda x: x.get("successes", 0) - x.get("failures", 0),
                        reverse=True)
        return ranked[:n]


_POS = ("正しい", "正解", "いいね", "良い", "よい", "ありがとう", "完璧", "その通り",
        "good", "correct", "thanks", "perfect", "right")
_NEG = ("違う", "間違い", "不正解", "だめ", "ダメ", "違うよ", "間違って", "嘘",
        "wrong", "incorrect", "bad", "no,", "いいえ", "そうじゃない", "もっと")


def looks_like_positive(text):
    t = text.strip().lower()
    return any(p.lower() in t for p in _POS) and not any(n.lower() in t for n in _NEG)


def looks_like_negative(text):
    t = text.strip().lower()
    return any(n.lower() in t for n in _NEG)


def looks_like_quality_feedback(text):
    """評議会回答への質フィードバック (ツール言及なしでも拾う)。"""
    return looks_like_positive(text) or looks_like_negative(text)
