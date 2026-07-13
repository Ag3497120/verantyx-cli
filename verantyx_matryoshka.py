"""
verantyx_matryoshka.py — 6軸マトリョーシカ・パズル推論
==============================================================================

プロンプトを表層1フォワードで6軸エネルギーに分解し、通った軸だけが
軸ディレクティブ付きで推論する。軸間の適合性グラフでパズル接合し、
外れ軸を捨てた合意を仮想トークンとして上位階層へ再注入する (入れ子)。
最終合意をルーター脳が発話する。

流れ (外→内→外):
  1. 素のプロンプトを1フォワードし、AxisAnchors 射影 (または次元区画) で
     6軸エネルギーを得る。ゲート未満の軸はスキップ (最低3軸は通す)
  2. ゲート通過軸をエネルギー降順で並べ、独立 opine (depth=0 は soft なし)
  3. DivergencePacket 交換 → PuzzleJoiner (閾値は乖離連動) で接合
  4. depth>0 のときだけ接合結果を soft 再注入
  5. speak_brain が合意概念つきで発話 (ClassifyOnlyBrain 禁止)

使い方:
  python3 verantyx_matryoshka.py --prompt "..." [--depth 2] [--gate 0.15] [--quiet]
"""

import argparse
import time

import numpy as np

from verantyx_mind import (
    RustBrain, JGenDict, AxisAnchors, AXIS_NAMES,
    DEFAULT_MODEL, TOKENIZER, HIDDEN,
    bar, C_SYS, C_THINK, C_SPEAK, C_MEM, C_RESET,
)
from verantyx_council import (
    role_tokens, dist_from_vector, dist_to_soft_numpy,
    polish_answer, resolve_tokens,
)

# AXIS_NAMES の並びと1対1対応 (ディレクティブは英語・推論用)
AXIS_DIRECTIVES = {
    "Logic/Structure": "Analyze the logical structure and constraints. State the single decisive answer.",
    "Syntax/Code": "Focus on formal, symbolic and syntactic aspects.",
    "Factual Memory": "Recall the most relevant established facts.",
    "Temporal/Time": "Consider temporal order, dates and causality.",
    "Creativity": "Consider unconventional interpretations and alternatives.",
    "Swarm Consensus": "Judge what most careful experts would agree on.",
}

# Phase 5: 軸キャリア最小注入 (人格フル学習ではない)
AXIS_CARRIER_ALPHA = 0.08


def _axis_key(name):
    """AXIS_NAMES のパディング空白を除いたキー。"""
    return name.strip()


# ── 軸スロット (同一脳をディレクティブで分化、将来は差し替え可) ──────────────
class AxisSlot:
    """軸1本。既定は共有ルーター脳 (brain/dict/tok を注入可能)。"""

    def __init__(self, name, directive, brain, dictionary, tok,
                 axis_index=None, axis_carrier=None, carrier_alpha=AXIS_CARRIER_ALPHA):
        self.name = name
        self.directive = directive
        self.brain = brain
        self.dict = dictionary
        self.tok = tok
        self.sem = None  # 遅延: semantic_mask
        self.axis_index = axis_index
        self.axis_carrier = axis_carrier  # (HIDDEN,) unit vector or None
        self.carrier_alpha = float(carrier_alpha)

    def opine(self, question, context_soft=None):
        """軸ディレクティブ付きで推論。(z, dist) を返す。
        context_soft: 埋め込み空間の仮想トークン (1, HIDDEN) or None。
        軸キャリアがある場合は隠れ状態へ小さい α で加算 (テキスト directive の代替ではない)。"""
        if self.sem is None:
            self.sem = self.dict.semantic_mask(self.tok)
        toks = role_tokens(self.tok, self.directive, question)
        if context_soft is not None:
            soft = np.asarray(context_soft, dtype=np.float32)
            if soft.ndim == 1:
                soft = soft[None, :]
            z = self.brain.encode_soft(soft, toks)
        else:
            z = self.brain.encode(toks)
        # 軸キャリア: 隠れ状態へ小さい α 加算 (soft 埋め込み次元とは独立)
        if self.axis_carrier is not None and self.carrier_alpha > 0:
            c = np.asarray(self.axis_carrier, dtype=np.float32).ravel()
            if c.shape[0] == np.asarray(z).shape[0]:
                zn = float(np.linalg.norm(z)) + 1e-8
                z = np.asarray(z, dtype=np.float32) + self.carrier_alpha * c * zn
        dist = dist_from_vector(self.dict, self.tok, z, self.sem)
        return z, dist


# ── パズル接合 (適合性グラフ → 最大クラスタ → 重み付き合意) ────────────────
class PuzzleJoiner:
    """軸間の適合性でクラスタを選び、外れ軸を捨てて合意分布を作る。"""

    def __init__(self, threshold=0.35):
        self.threshold = threshold

    @staticmethod
    def _dist_overlap(dist_a, dist_b):
        """正規化文字列トークンの確率重み付き共通質量。"""
        ma, mb = {}, {}
        for s, w in dist_a:
            k = s.strip().lower()
            if k:
                ma[k] = ma.get(k, 0.0) + w
        for s, w in dist_b:
            k = s.strip().lower()
            if k:
                mb[k] = mb.get(k, 0.0) + w
        return float(sum(min(ma[k], mb[k]) for k in ma if k in mb))

    @staticmethod
    def _cos(a, b):
        a = np.asarray(a, dtype=np.float32).ravel()
        b = np.asarray(b, dtype=np.float32).ravel()
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def join(self, axis_results, energies, threshold=None):
        """axis_results: [(axis_name, z, dist), ...] (ゲート通過軸のみ)。
        energies: {axis_name: float} (正規化済みエネルギー)。
        threshold: 乖離連動で上書き可。クラスタサイズ<2 のときのみ全採用フォールバック。"""
        thr = self.threshold if threshold is None else float(threshold)
        n = len(axis_results)
        if n == 0:
            return {"dist": [], "joined": [], "dropped": [], "compat": [],
                    "threshold": thr}

        names = [r[0] for r in axis_results]
        zs = [r[1] for r in axis_results]
        dists = [r[2] for r in axis_results]

        compat = np.zeros((n, n), dtype=np.float32)
        for i in range(n):
            compat[i, i] = 1.0
            for j in range(i + 1, n):
                c = 0.5 * self._cos(zs[i], zs[j]) + 0.5 * self._dist_overlap(dists[i], dists[j])
                compat[i, j] = compat[j, i] = c

        # 平均適合が最大のノードを種に、閾値以上を貪欲に加える
        avg = compat.mean(axis=1)
        seed = int(np.argmax(avg))
        cluster = {seed}
        for i in range(n):
            if i != seed and compat[seed, i] >= thr:
                cluster.add(i)
        # 1軸しか残らなければ全軸採用にフォールバック (クラスタサイズ<2 のときのみ)
        fallback_full = False
        if len(cluster) < 2 and n >= 2:
            cluster = set(range(n))
            fallback_full = True

        joined_idx = sorted(cluster)
        dropped_idx = [i for i in range(n) if i not in cluster]
        joined = [names[i] for i in joined_idx]
        dropped = [names[i] for i in dropped_idx]

        # 合意分布: energy * (種との適合 + ε) で重み付きマージ
        merged = {}
        for i in joined_idx:
            w_axis = float(energies.get(names[i], 0.0)) * (float(compat[seed, i]) + 1e-3)
            for s, w in dists[i]:
                nk = s.strip().lower()
                if not nk:
                    continue
                hit = next((kk for kk in merged if kk.strip().lower() == nk), None)
                if hit is None:
                    merged[s] = w_axis * w
                else:
                    merged[hit] += w_axis * w

        items = sorted(merged.items(), key=lambda kv: -kv[1])[:48]
        total = sum(w for _, w in items) + 1e-12
        dist = [(s, w / total) for s, w in items]

        return {
            "dist": dist,
            "joined": joined,
            "dropped": dropped,
            "compat": compat.tolist(),
            "seed": names[seed],
            "threshold": thr,
            "fallback_full": fallback_full,
        }


# ── マトリョーシカ評議会 ────────────────────────────────────────────────────
class MatryoshkaCouncil:
    """表層分解 → 軸推論 → パズル接合 → 入れ子 → ルーター発話。"""

    def __init__(self, quiet=False, brain=None, dictionary=None, tok=None, axes=None,
                 carrier_alpha=AXIS_CARRIER_ALPHA, enable_lexicon=None):
        from transformers import AutoTokenizer
        self.quiet = quiet
        self._owns_brain = brain is None
        if brain is not None and dictionary is not None and tok is not None:
            self.brain = brain
            self.dict = dictionary
            self.tok = tok
        else:
            self.tok = AutoTokenizer.from_pretrained(TOKENIZER)
            self.dict = JGenDict(DEFAULT_MODEL)
            self.brain = RustBrain(DEFAULT_MODEL)
            try:
                from memory_guard import GUARD as _guard
                _guard.register_trimmable("jgen:matryoshka", self.brain.trim)
            except Exception:
                pass
        # speak / deliberate 論理分離 (同一ウェイト・ClassifyOnly 禁止)
        self.deliberate_brain = self.brain
        self.speak_brain = self.brain
        self.axes = axes if axes is not None else AxisAnchors()
        self.joiner = PuzzleJoiner()
        self.carrier_alpha = float(carrier_alpha)
        self.slots = []
        for i, raw_name in enumerate(AXIS_NAMES):
            key = _axis_key(raw_name)
            directive = AXIS_DIRECTIVES.get(key, "Give your careful judgment.")
            carrier = None
            if self.axes.available and hasattr(self.axes, "anchors"):
                try:
                    carrier = np.asarray(self.axes.anchors[i], dtype=np.float32)
                except Exception:
                    carrier = None
            self.slots.append(AxisSlot(
                key, directive, self.deliberate_brain, self.dict, self.tok,
                axis_index=i, axis_carrier=carrier,
                carrier_alpha=self.carrier_alpha if carrier is not None else 0.0,
            ))
        # Phase 5: 命題レキシコン (puzzle_div のみ既定 on。旧 puzzle は off)
        self.lexicon = None
        if enable_lexicon is None:
            enable_lexicon = carrier_alpha > 0
        if enable_lexicon:
            try:
                import os
                from concept_lexicon import ConceptLexicon, LEXICON_PATH, codec_enabled
                if codec_enabled() and os.path.exists(LEXICON_PATH):
                    self.lexicon = ConceptLexicon(LEXICON_PATH)
            except Exception:
                self.lexicon = None
        self._last_divergence = None
        self._last_divergence_packets = []

    def log(self, msg):
        if not self.quiet:
            print(msg)

    def decompose(self, question):
        """素のプロンプト1フォワード → 6軸エネルギー (6,)。"""
        toks = role_tokens(self.tok, "You are a helpful assistant.", question)
        z = self.deliberate_brain.encode(toks)
        if self.axes.available:
            sig = self.axes.signature(z)  # anchors @ ((z-mu)/||...||)
            lo, hi = float(sig.min()), float(sig.max())
            energies = (sig - lo) / (hi - lo + 1e-8)
            energies = np.clip(energies, 0.0, 1.0).astype(np.float32)
        else:
            # 未学習時: 次元区画ごとの平均絶対値 (verantyx_mind の慣例)
            chunk = HIDDEN // 6
            raw = []
            for i in range(6):
                seg = z[i * chunk: (i + 1) * chunk] if i < 5 else z[i * chunk:]
                raw.append(float(np.abs(seg).mean()))
            peak = max(raw) + 1e-8
            energies = np.asarray([e / peak for e in raw], dtype=np.float32)
        return energies

    def _gate_axes(self, energies, gate, energy_order=True):
        """正規化エネルギーでゲート。最低3軸は上位から必ず通す。

        energy_order=True: エネルギー降順 (puzzle_div)。
        energy_order=False: 軸インデックス昇順 (旧 puzzle 互換)。
        """
        e = np.asarray(energies, dtype=np.float32)
        e = e / (e.sum() + 1e-8)
        order = list(np.argsort(-e))  # 降順
        keep = set()
        for i in order[:3]:
            keep.add(int(i))
        for i in range(6):
            if e[i] >= gate:
                keep.add(i)
        if energy_order:
            keep_sorted = [i for i in order if i in keep]
        else:
            keep_sorted = sorted(keep)
        return keep_sorted, e

    def _concepts_from_dist(self, dist, k=5):
        """合意分布から半角英数の意味トークンを上位 k 個。"""
        concepts, seen = [], set()
        for s, _ in dist:
            body = s.strip()
            key = body.lower().lstrip("-_")
            if len(body) < 2 or key in seen:
                continue
            # 半角英数を含む意味のある文字列のみ
            if not any(c.isalnum() and ord(c) < 128 for c in body):
                continue
            if not any(c.isalnum() for c in body):
                continue
            seen.add(key)
            concepts.append(body)
            if len(concepts) >= k:
                break
        return concepts

    def _speak(self, question, concepts, speak_tokens="auto"):
        """speak_brain で合意概念つき発話。ClassifyOnlyBrain 禁止。"""
        from router_classifier import ClassifyOnlyBrain
        if isinstance(self.speak_brain, ClassifyOnlyBrain):
            raise RuntimeError(
                "Matryoshka._speak: speak_brain must not be ClassifyOnlyBrain")
        max_new = resolve_tokens(speak_tokens, small=True)
        sys_p = "You are a helpful assistant."
        if concepts:
            sys_p += " Council consensus concepts: " + ", ".join(concepts) + "."
        pr = (f"<|im_start|>system\n{sys_p}<|im_end|>\n"
              f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n")
        out = self.speak_brain.generate(
            self.tok.encode(pr, add_special_tokens=False), max_new)
        return polish_answer(self.tok.decode(out, skip_special_tokens=True).strip())

    def ask(self, question, depth=2, gate=0.15, speak_tokens="auto",
            use_divergence=False):
        """use_divergence=False: 旧 puzzle 本線 (固定接合閾値・乖離交換なし)。
        use_divergence=True: puzzle_div (DivergencePacket + C/E/R/N + 乖離連動 join)。
        """
        from divergence_packet import packet_from_hidden_dist, packets_to_serializable

        t0 = time.time()
        energies_raw = self.decompose(question)
        keep_idx, energies_norm = self._gate_axes(
            energies_raw, gate, energy_order=use_divergence)
        axis_energies = {_axis_key(AXIS_NAMES[i]): float(energies_norm[i]) for i in range(6)}

        self.log(f"\n{C_THINK}━━ [表層] 6軸エネルギー分解 ━━{C_RESET}")
        for i in range(6):
            name = _axis_key(AXIS_NAMES[i])
            mark = " ✓" if i in keep_idx else " (gate)"
            self.log(f"{C_THINK}  {name}: {bar(float(energies_norm[i]))} "
                     f"{energies_norm[i]:.3f}{mark}{C_RESET}")
        order_names = [_axis_key(AXIS_NAMES[i]) for i in keep_idx]
        order_label = "energy↓" if use_divergence else "index↑"
        self.log(f"{C_SYS}  渡し順 ({order_label}): {order_names}{C_RESET}")

        # エネルギー降順のスロット列
        active = [self.slots[i] for i in keep_idx]
        energy_map = {s.name: axis_energies[s.name] for s in active}

        # depth=0: context_soft=None。join 後のみ depth>0 に soft 注入
        context_soft = None
        last_join = {"joined": [], "dropped": [], "dist": []}
        divergence_packets = []
        exchange_trace = None
        axis_results = []

        for d in range(depth):
            self.log(f"\n{C_SYS}━━ [階層 {d + 1}/{depth}] 軸推論 → パズル接合 ━━{C_RESET}")
            # puzzle_div: depth0 は独立。旧 puzzle: join soft を次 depth へ (初回 None)
            if use_divergence:
                soft_this = None if d == 0 else context_soft
            else:
                soft_this = context_soft
            axis_results = []
            packets = []
            zs, dists = {}, {}
            for slot in active:
                z, dist = slot.opine(question, soft_this)
                axis_results.append((slot.name, z, dist))
                zs[slot.name] = z
                dists[slot.name] = dist
                top = ", ".join(f"{s.strip()}:{w:.2f}" for s, w in dist[:4])
                self.log(f"{C_THINK}  [{slot.name}] {top}{C_RESET}")

            if use_divergence:
                from divergence_exchange import (
                    exchange_packets, join_threshold_for_divergence,
                    proposition_hint_text,
                )
                packets = []
                for slot_name, z, dist in axis_results:
                    packets.append(packet_from_hidden_dist(
                        slot_name, z, dist, axis=slot_name,
                        dictionary=self.dict, tok=self.tok))

                exchange = exchange_packets(packets, zs=zs, dists=dists)
                exchange_trace = exchange.trace_dict()
                join_thr = join_threshold_for_divergence(exchange.divergence)
                last_join = self.joiner.join(
                    axis_results, energy_map, threshold=join_thr)
                joined = last_join["joined"]
                dropped = last_join["dropped"]
                self.log(f"{C_MEM}  [Divergence] div={exchange.divergence:.3f} "
                         f"action={exchange.action} join_thr={join_thr:.3f}{C_RESET}")
                self.log(f"{C_MEM}  接合: ハマった={joined} / 外れた={dropped}{C_RESET}")

                if exchange.action == "reinfer" and exchange.split_roles and d == 0:
                    hint = proposition_hint_text(packets, exchange.split_roles)
                    try:
                        e_rows = np.asarray(self.dict._embed_f16, dtype=np.float32)
                        hint_ids = self.tok.encode(
                            f"<|im_start|>system\nReconcile: {hint}<|im_end|>\n",
                            add_special_tokens=False)
                        ids = [i for i in hint_ids if 0 <= i < len(e_rows)][:48]
                        if ids:
                            hint_soft = e_rows[ids].mean(axis=0, keepdims=True)
                            split_set = set(exchange.split_roles)
                            axis_results2 = []
                            packets2 = []
                            for slot in active:
                                soft_r = hint_soft if slot.name in split_set else None
                                z, dist = slot.opine(question, soft_r)
                                axis_results2.append((slot.name, z, dist))
                                zs[slot.name] = z
                                dists[slot.name] = dist
                                packets2.append(packet_from_hidden_dist(
                                    slot.name, z, dist, axis=slot.name,
                                    dictionary=self.dict, tok=self.tok))
                            exchange = exchange_packets(
                                packets2, zs=zs, dists=dists, reinfer_done=True)
                            exchange_trace = exchange.trace_dict()
                            join_thr = join_threshold_for_divergence(
                                exchange.divergence)
                            last_join = self.joiner.join(
                                axis_results2, energy_map, threshold=join_thr)
                            axis_results = axis_results2
                            packets = packets2
                            self.log(
                                f"{C_MEM}  [Divergence] reinfer → "
                                f"div={exchange.divergence:.3f} "
                                f"dropped={last_join['dropped']}{C_RESET}")
                    except Exception as e:
                        self.log(f"{C_MEM}  [Divergence] reinfer failed: {e}{C_RESET}")

                divergence_packets = packets
            else:
                # 旧 puzzle: 固定閾値 0.35、乖離交換なし
                last_join = self.joiner.join(axis_results, energy_map)
                joined = last_join["joined"]
                dropped = last_join["dropped"]
                self.log(f"{C_MEM}  接合: ハマった={joined} / 外れた={dropped}{C_RESET}")

            cloud = ", ".join(f"{s.strip()}({w:.2f})" for s, w in last_join["dist"][:8])
            self.log(f"{C_MEM}  合意トークン雲: {cloud}{C_RESET}")

            lexicon_hits = []
            if use_divergence and self.lexicon and self.lexicon.available and axis_results:
                mean_z = np.mean([z for _, z, _ in axis_results], axis=0)
                lexicon_hits = self.lexicon.read(mean_z, top_k=3)
                self.log(f"{C_MEM}  レキシコン: "
                         + ", ".join(f"{lab[:40]}({sc:.2f})" for lab, sc in lexicon_hits)
                         + C_RESET)

            # depth>0 への soft は join 後のみ
            if d + 1 < depth and last_join["dist"]:
                e = dist_to_soft_numpy(last_join["dist"], self.tok, self.dict._embed_f16)
                if use_divergence:
                    softs = [e]
                    if (lexicon_hits and "Factual Memory" in joined
                            and lexicon_hits[0][1] > 0.2):
                        try:
                            lab = lexicon_hits[0][0]
                            direction = self.lexicon.write(lab, scale=10.0)
                            dlex = dist_from_vector(
                                self.dict, self.tok, direction,
                                self.dict.semantic_mask(self.tok), top_k=24)
                            softs.append(dist_to_soft_numpy(
                                dlex, self.tok, self.dict._embed_f16))
                        except Exception:
                            pass
                    context_soft = np.stack(softs, axis=0)
                else:
                    # 旧 puzzle: 単一 soft (1, HIDDEN)
                    context_soft = e[None, :]

        concepts = self._concepts_from_dist(last_join.get("dist") or [], k=5)
        lexicon_labels = []
        if use_divergence and axis_results:
            try:
                from concept_lexicon import ConceptLexicon
                lex = ConceptLexicon()
                if lex.available:
                    z_mean = np.mean([z for _, z, _ in axis_results], axis=0)
                    for lab, sc in lex.read(z_mean, top_k=2):
                        if sc > 0.15:
                            lexicon_labels.append(lab)
                            short = lab if len(lab) < 48 else lab[:45] + "..."
                            if short not in concepts:
                                concepts.append(short)
            except Exception:
                pass

        if use_divergence:
            self._last_divergence = exchange_trace
            self._last_divergence_packets = packets_to_serializable(
                divergence_packets)
        else:
            self._last_divergence = None
            self._last_divergence_packets = []

        self.log(f"\n{C_SPEAK}━━ [Speaker] router(matryoshka) が発話 ━━{C_RESET}")
        answer = self._speak(question, concepts, speak_tokens=speak_tokens)
        self.log(f"{C_SPEAK}  🤖 {answer}{C_RESET}")

        elapsed = round(time.time() - t0, 1)
        self.log(f"{C_SYS}  ({elapsed}s, depth={depth}, "
                 f"joined={last_join.get('joined')}){C_RESET}")

        return {
            "answer": answer,
            "speaker": "router(matryoshka)",
            "rounds": depth,
            "elapsed_s": elapsed,
            "concepts": concepts,
            "lexicon_labels": lexicon_labels,
            "axis_energies": axis_energies,
            "joined_axes": last_join.get("joined", []),
            "dropped_axes": last_join.get("dropped", []),
            "pass_order": order_names,
            "divergence_packets": self._last_divergence_packets,
            "divergence": self._last_divergence,
            "join_threshold": last_join.get("threshold"),
            "use_divergence": use_divergence,
        }

    def close(self):
        if self._owns_brain and self.brain is not None:
            self.brain.close()
            self.brain = None


def main():
    ap = argparse.ArgumentParser(description="6軸マトリョーシカ・パズル推論")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--gate", type=float, default=0.15)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--speak-tokens", default="auto")
    args = ap.parse_args()

    print(f"{C_SYS}╔═══════════════════════════════════════════════╗")
    print(f"║  Verantyx Matryoshka — Puzzle Inference        ║")
    print(f"╚═══════════════════════════════════════════════╝{C_RESET}")

    council = MatryoshkaCouncil(quiet=args.quiet)
    try:
        rec = council.ask(args.prompt, depth=args.depth, gate=args.gate,
                          speak_tokens=args.speak_tokens)
        print(f"\n{C_SPEAK}answer: {rec['answer']}{C_RESET}")
        print(f"{C_SYS}speaker={rec['speaker']}  elapsed={rec['elapsed_s']}s  "
              f"depth={rec['rounds']}{C_RESET}")
        print(f"{C_SYS}concepts={rec['concepts']}{C_RESET}")
        print(f"{C_SYS}joined={rec['joined_axes']}  dropped={rec['dropped_axes']}{C_RESET}")
        print(f"{C_SYS}pass_order={rec.get('pass_order')}{C_RESET}")
        print(f"{C_SYS}energies={{{', '.join(f'{k}:{v:.3f}' for k, v in rec['axis_energies'].items())}}}{C_RESET}")
        if rec.get("divergence"):
            print(f"{C_SYS}divergence action={rec['divergence'].get('action')} "
                  f"div={rec['divergence'].get('divergence')}{C_RESET}")
    finally:
        council.close()


if __name__ == "__main__":
    main()
