"""
router_reflex.py — ルーターの進化層 (反射 = スキル獲得によるステップ数削減)
==============================================================================
哲学: ルーター (0.5B) はソフトウェア並みに軽く常駐し、簡単なことは自分で
処理し、経験によって「進化」する。ここでの進化は重みの勾配更新ではなく、
問題ベクトル → 最適ルートの対応を永続化する反射弓 (reflex arc) として実装する。

  1回目: 議論4ラウンド + エスカレーション2段 = 60秒かかった問題も、
  2回目: 類似ベクトルの反射が発火 → 必要な階層を最初から招集、
         ラウンド上限を絞る、あるいはエージェント直行 = ステップ数が減る。

これはユーザーのペルソナ (よく聞く分野) に合わせてルーターが分野スキルを
獲得していくことと等価。記録は .verantyx_chrono に永続化され、発火する
たびに強化される (hits)。ズレ (摂動テストで合意が壊れた記録) も刻まれ、
脆かった問題は次回から深い議論を最初から要求する。
"""

import json
import os
import time

import numpy as np

CHRONO = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono")
REFLEX_VEC = os.path.join(CHRONO, "reflex.vectors")
REFLEX_IDX = os.path.join(CHRONO, "reflex.index.jsonl")
DIM = 1024
SIM_FIRE = 0.86        # これ以上似ていたら反射が発火する


class RouterReflex:
    def __init__(self):
        os.makedirs(CHRONO, exist_ok=True)
        self.index = []
        if os.path.exists(REFLEX_IDX):
            with open(REFLEX_IDX) as f:
                self.index = [json.loads(l) for l in f if l.strip()]
        self._vecs = None

    def _vectors(self):
        if self._vecs is None and os.path.exists(REFLEX_VEC):
            self._vecs = np.fromfile(REFLEX_VEC, dtype=np.float32).reshape(-1, DIM)
        return self._vecs if self._vecs is not None else np.zeros((0, DIM), np.float32)

    # ── 想起 (発火判定) ──
    def fire(self, qvec, k=3):
        """類似の過去経験を返す。[(node, sim), ...] 降順。"""
        V = self._vectors()
        if len(V) == 0:
            return []
        qn = np.asarray(qvec, dtype=np.float32)
        qn = qn / (np.linalg.norm(qn) + 1e-8)
        sims = V @ qn
        order = np.argsort(sims)[::-1][:k]
        return [(self.index[i], float(sims[i])) for i in order if sims[i] >= SIM_FIRE]

    def advise(self, qvec):
        """反射弓: 過去の類似経験からショートカット指令を合成する。
        返り値 dict:
          intent       : 'task' なら評議会を通さずエージェント直行
          pre_escalate : 最初から招集すべき階層 (0-2)。無駄なラウンドを省く
          max_rounds   : 過去に頑健に即決した問題なら上限を絞る
          fragile      : 過去にズレ耐性がなかった問題 (深い議論を最初から要求)
        """
        hits = self.fire(qvec)
        if not hits:
            return None
        # 類似度が主、発火回数 (強化) はタイブレーク程度の弱い加点に留める
        def w(h):
            return h[1] + 0.02 * min(h[0].get("hits", 0), 5)
        best = max(hits, key=w)
        node, sim = best
        advice = {
            "sim": sim,
            "intent": node.get("intent", "chat"),
            "pre_escalate": int(node.get("esc_level", 0)),
            "fragile": bool(node.get("fragile", False)),
            "max_rounds": None,
            "src": node.get("question", "")[:40],
        }
        # 頑健 (摂動に耐えた) かつ 1-2 ラウンドで決着した経験 → 反射的即決
        if not advice["fragile"] and node.get("rounds", 4) <= 2:
            advice["max_rounds"] = 2
        self._reinforce(node["id"])
        return advice

    def _reinforce(self, node_id):
        """発火した反射を強化する (使うほど強く・速くなる)。"""
        for n in self.index:
            if n["id"] == node_id:
                n["hits"] = n.get("hits", 0) + 1
                break
        self._flush()

    # ── 刻印 (経験の獲得) ──
    def record(self, qvec, question, intent="chat", esc_level=0, rounds=0,
               fragile=False, elapsed_s=0.0):
        node = {
            "id": len(self.index), "ts": time.time(),
            "question": question[:160], "intent": intent,
            "esc_level": int(esc_level), "rounds": int(rounds),
            "fragile": bool(fragile), "elapsed_s": round(float(elapsed_s), 1),
            "hits": 0,
        }
        v = np.asarray(qvec, dtype=np.float32)
        v = v / (np.linalg.norm(v) + 1e-8)
        with open(REFLEX_VEC, "ab") as f:
            v.tofile(f)
        with open(REFLEX_IDX, "a") as f:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")
        self.index.append(node)
        self._vecs = None
        return node

    def _flush(self):
        with open(REFLEX_IDX, "w") as f:
            for n in self.index:
                f.write(json.dumps(n, ensure_ascii=False) + "\n")

    def stats(self):
        total_hits = sum(n.get("hits", 0) for n in self.index)
        return {"reflexes": len(self.index), "fires": total_hits,
                "fragile": sum(1 for n in self.index if n.get("fragile"))}


if __name__ == "__main__":
    r = RouterReflex()
    print("[Reflex]", r.stats())
