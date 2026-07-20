"""scale_substrate.py — パラメータ級スケールアップの外付け基盤
==============================================================================

目的:
  話者 (小さいモデル) と、記憶を育てる監査/ライター (一段大きいモデル) を
  分離し、モデル切替時も MemoryGraph 正本がついてくるようにする。

  0.5B speaker + 9B auditor/writer  ≈ 単体 9B に寄せる土台
  9B speaker  + 14B-class auditor ≈ 一段上に寄せる土台

役割:
  speaker   … 最終発話 (軽く常駐)
  auditor   … グラフ結論の検算・パッチ (ローカル大型 / frontier)
  writer    … Dream / 構造化 ingest の既定書き手ヒント (通常は auditor と同じ)
  memory    … MemoryGraph 永遠記憶 (モデル非依存の正本)

切替は「重みの移植」ではなく「誰がグラフを育てるか」の付け替え。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ScaleRoles:
    speaker: str = "router"       # router | worker | sage | bridge:…
    auditor: str = "auto"         # auto | sage | bridge | worker | none
    writer: str = "auto"          # auto (=auditor) | …
    frontier: str = ""            # VERANTYX_FRONTIER_AUDITOR と同義の表示用
    notes: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "speaker": self.speaker,
            "auditor": self.auditor,
            "writer": self.writer,
            "frontier": self.frontier or frontier_env(),
            "notes": dict(self.notes),
        }


def frontier_env() -> str:
    return (os.environ.get("VERANTYX_FRONTIER_AUDITOR") or "").strip()


def bind_scale_roles(council, roles: Optional[ScaleRoles] = None) -> ScaleRoles:
    """council にスケール役割をバインド。実体のロードは既存 escalate/bridge に委譲。"""
    roles = roles or infer_roles(council)
    council._scale_roles = roles
    return roles


def infer_roles(council) -> ScaleRoles:
    """現在ロード済み参加者から役割を推定。"""
    speaker = "router"
    if getattr(council, "_force_router_speaker", False):
        speaker = "router"
    elif getattr(council, "_sage", None) is not None:
        # sage が居ても話者は設定次第 — 既定は「小さい話者」を推奨表示
        speaker = "router"
    if getattr(council, "_worker", None) is not None:
        # worker があるなら話者候補として記録 (実際の speak 選択は council.speak)
        pass

    auditor = "none"
    if getattr(council, "_sage", None) is not None:
        auditor = "sage:" + getattr(council._sage, "name", "sage")
    elif getattr(council, "_bridges", None):
        b0 = council._bridges[0]
        auditor = "bridge:" + getattr(b0, "name", "bridge")
    elif getattr(council, "_worker", None) is not None:
        auditor = "worker:" + getattr(council._worker, "name", "worker")

    # env で話者を小さく固定するヒント
    env_speaker = (os.environ.get("VERANTYX_SCALE_SPEAKER") or "").strip().lower()
    if env_speaker in ("router", "0.5b", "small"):
        speaker = "router"
    elif env_speaker in ("worker", "9b"):
        speaker = "worker"
    elif env_speaker.startswith("bridge") or env_speaker == "sage":
        speaker = env_speaker

    env_aud = (os.environ.get("VERANTYX_SCALE_AUDITOR") or "").strip().lower()
    if env_aud == "none":
        auditor = "none"
    elif env_aud in ("auto", ""):
        pass
    else:
        auditor = env_aud

    writer = auditor if auditor != "none" else "graph_only"
    env_writer = (os.environ.get("VERANTYX_SCALE_WRITER") or "").strip().lower()
    if env_writer:
        writer = env_writer

    return ScaleRoles(
        speaker=speaker,
        auditor=auditor,
        writer=writer,
        frontier=frontier_env(),
        notes={
            "memory_canonical": "MemoryGraph",
            "vector_optional": True,
            "goal": "small_speaker_plus_grown_graph ≈ larger_monolith",
        },
    )


def ensure_auditor(council, *, prefer_bridge: bool = True) -> Dict[str, Any]:
    """監査役がいなければ bridge を自動接続を試みる (ロードは重い sage は触らない)。"""
    from graph_auditor import select_local_auditor
    p, name = select_local_auditor(council)
    if p is not None:
        return {"ok": True, "auditor": name, "action": "existing"}
    if not prefer_bridge:
        return {"ok": False, "reason": "no_auditor"}
    try:
        from verantyx_bridges import detect_backends
        found = detect_backends()
        spec = None
        if found.get("lmstudio"):
            spec = "lmstudio"
        elif found.get("ollama"):
            spec = "ollama"
        if not spec:
            return {"ok": False, "reason": "no_local_llm_server"}
        if hasattr(council, "add_bridge"):
            council.add_bridge(spec)
            p2, name2 = select_local_auditor(council)
            bind_scale_roles(council)
            return {"ok": p2 is not None, "auditor": name2, "action": f"add_bridge:{spec}"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:160]}
    return {"ok": False, "reason": "attach_failed"}


def scale_status(council) -> Dict[str, Any]:
    """基盤の現状スナップショット。"""
    roles = getattr(council, "_scale_roles", None) or infer_roles(council)
    mem = getattr(council, "memory", None)
    n_mem = len(getattr(mem, "index", None) or []) if mem and getattr(mem, "enabled", False) else 0
    n_audited = 0
    n_dream = 0
    if mem and getattr(mem, "enabled", False):
        for rec in (mem.index or [])[-200:]:
            k = rec.get("kind") or ""
            if "audit" in k:
                n_audited += 1
            if str(k).startswith("dream"):
                n_dream += 1
            g = rec.get("graph") or {}
            ts = (g.get("meta") or {}).get("truth_status") or rec.get("truth_status")
            if ts == "audited":
                n_audited += 1
    from graph_auditor import select_local_auditor
    _p, aname = select_local_auditor(council)
    return {
        "roles": roles.as_dict(),
        "auditor_live": aname or None,
        "memory_enabled": bool(mem and getattr(mem, "enabled", False)),
        "memory_nodes": n_mem,
        "dream_nodes_recent": n_dream,
        "audited_signal_recent": n_audited,
        "frontier": frontier_env() or None,
        "env": {
            "VERANTYX_SCALE_SPEAKER": os.environ.get("VERANTYX_SCALE_SPEAKER"),
            "VERANTYX_SCALE_AUDITOR": os.environ.get("VERANTYX_SCALE_AUDITOR"),
            "VERANTYX_DREAM_AFTER_ASK": os.environ.get("VERANTYX_DREAM_AFTER_ASK"),
            "VERANTYX_AUDIT_AFTER_ASK": os.environ.get("VERANTYX_AUDIT_AFTER_ASK"),
            "VERANTYX_FRONTIER_AUDITOR": os.environ.get("VERANTYX_FRONTIER_AUDITOR"),
        },
        "thesis": (
            "Keep a small speaker; grow MemoryGraph with a larger auditor/writer; "
            "switch models without re-embedding the canonical graph."
        ),
    }


def migrate_hint() -> Dict[str, str]:
    """運用チートシート (コードから /scale で表示)。"""
    return {
        "grow_with_9b": (
            "1) /bridge ollama:<9b-or-larger> or load sage/worker\n"
            "2) /dream N   # pre-resolve + rival\n"
            "3) audits run if auditor present\n"
            "4) set VERANTYX_SCALE_SPEAKER=router and speak with 0.5B\n"
            "5) memory graph remains; 0.5B reads grounds/lock"
        ),
        "canonical": "MemoryGraph (concepts/propositions/candidates/grounds/edges)",
        "do_not": "Do not treat raw hidden states as the memory source of truth across models",
    }
