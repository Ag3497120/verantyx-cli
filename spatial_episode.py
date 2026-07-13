"""
spatial_episode.py — Capture InteractionRecord → SpatialEpisode / 空間操作コア(最小)
==============================================================================

Capture (open-object-house) が書き出したパッケージを読み、
机〜部屋スケールの操作記憶として使える形に畳む。

分業 (docs/CAPTURE_SYNC.md):
  Capture = UI・収録・Export
  本モジュール = インポート・SpatialEpisode・Locate/Return/Relation

LLM フル再学習はしない。ここではグラフ + 軌道の数値コアのみ。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np

# Capture 実機語彙 (lift/restore/articulate…) を含む。return は restore の別名として扱う。
ACTION_LABELS = (
    "register", "extract", "place", "return", "restore", "drop",
    "open", "close", "fold", "lift", "articulate", "relocate", "other",
)

RETURN_LABELS = frozenset({"return", "restore"})


def _yaw_to_quat(degrees: float) -> np.ndarray:
    """Y 軸回転 (度) → quat [x,y,z,w]。Capture の rotationYDegrees 用。"""
    half = np.deg2rad(float(degrees)) * 0.5
    return np.array([0.0, np.sin(half), 0.0, np.cos(half)], dtype=np.float32)


def _pose_vec(pose: Optional[dict]) -> Optional[np.ndarray]:
    """position(3)+rotation → float32[7]。
    rotation は quat 配列、または Capture の rotationYDegrees。"""
    if not pose or not isinstance(pose, dict):
        return None
    pos = pose.get("position") or pose.get("pos")
    if pos is None:
        return None
    p = np.asarray(pos, dtype=np.float32).reshape(-1)[:3]
    if p.shape[0] < 3:
        p = np.pad(p, (0, 3 - p.shape[0]))
    rot = pose.get("rotation") or pose.get("quat") or pose.get("orientation")
    if rot is not None:
        q = np.asarray(rot, dtype=np.float32).reshape(-1)[:4]
        if q.shape[0] < 4:
            q = np.pad(q, (0, 4 - q.shape[0]))
            if abs(float(q[3])) < 1e-8 and np.allclose(q[:3], 0):
                q[3] = 1.0
    elif "rotationYDegrees" in pose:
        q = _yaw_to_quat(pose.get("rotationYDegrees") or 0)
    else:
        q = np.array([0, 0, 0, 1], dtype=np.float32)
    return np.concatenate([p, q]).astype(np.float32)


def _traj_latent(traj: Any, out_dim: int = 32) -> np.ndarray:
    """疎な motionTrajectory を固定長ベクトルへ (平均・標準・始端・終端)。
    Capture は position と objectPosition の両方を持つことがある。"""
    z = np.zeros(out_dim, dtype=np.float32)
    if not traj:
        return z
    pts = []
    for step in traj:
        if isinstance(step, dict):
            pos = (step.get("position") or step.get("objectPosition")
                   or step.get("pos") or step.get("object_position"))
            if pos is not None:
                pts.append(np.asarray(pos, dtype=np.float32).reshape(-1)[:3])
        elif isinstance(step, (list, tuple)) and len(step) >= 3:
            pts.append(np.asarray(step[:3], dtype=np.float32))
    if not pts:
        return z
    arr = np.stack(pts, axis=0)
    feats = [
        arr.mean(axis=0),
        arr.std(axis=0),
        arr[0],
        arr[-1],
        arr[-1] - arr[0],
    ]
    flat = np.concatenate(feats).astype(np.float32)
    n = min(out_dim, flat.shape[0])
    z[:n] = flat[:n]
    return z


def _normalize_action(label: Optional[str]) -> str:
    key = str(label or "other").strip().lower()
    if key == "return":
        return "restore"  # Capture 語彙に寄せる (意味は同じ)
    return key if key else "other"


def _action_onehot(label: Optional[str]) -> np.ndarray:
    v = np.zeros(len(ACTION_LABELS), dtype=np.float32)
    key = _normalize_action(label)
    if key in ACTION_LABELS:
        v[ACTION_LABELS.index(key)] = 1.0
    else:
        v[ACTION_LABELS.index("other")] = 1.0
    return v


@dataclass
class InteractionRecord:
    raw: dict
    record_id: str
    object_id: str
    room_id: str
    container_id: Optional[str]
    action_label: str
    pose_home: Optional[np.ndarray]
    pose_before: Optional[np.ndarray]
    pose_after: Optional[np.ndarray]
    trajectory_latent: np.ndarray
    user_correction: Optional[dict]
    display_name: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "InteractionRecord":
        rid = str(d.get("recordID") or d.get("id") or d.get("record_id") or "")
        oid = str(d.get("objectID") or d.get("object_id") or "")
        room = str(d.get("roomID") or d.get("room_id") or "")
        cid = d.get("containerID") or d.get("container_id")
        label = _normalize_action(d.get("actionLabel") or d.get("action_label") or "other")
        name = d.get("displayName") or d.get("display_name")
        uc = d.get("userCorrection") or d.get("user_correction")
        traj = d.get("motionTrajectory") or d.get("motion_trajectory") or []
        return cls(
            raw=d,
            record_id=rid or f"anon_{oid}_{label}",
            object_id=oid,
            room_id=room,
            container_id=str(cid) if cid else None,
            action_label=label,
            pose_home=_pose_vec(d.get("poseHome") or d.get("pose_home")),
            pose_before=_pose_vec(d.get("poseBefore") or d.get("pose_before")),
            pose_after=_pose_vec(d.get("poseAfter") or d.get("pose_after")),
            trajectory_latent=_traj_latent(traj),
            user_correction=uc if isinstance(uc, dict) else None,
            display_name=str(name) if name else None,
        )


@dataclass
class SpatialEpisode:
    """InteractionRecord を立体十字スロット風の固定表現に畳んだもの。"""
    record_id: str
    object_id: str
    room_id: str
    container_id: Optional[str]
    action_label: str
    action_axis: list  # one-hot list
    pose_home: Optional[list]
    pose_before: Optional[list]
    pose_after: Optional[list]
    trajectory_latent: list
    relation_axes: dict  # in/on の粗い旗
    drop_flag: bool
    display_name: Optional[str] = None
    meta: dict = field(default_factory=dict)

    def vector(self, dim: int = 64) -> np.ndarray:
        """検索・近傍用の連結ベクトル (固定長)。"""
        parts = [
            _action_onehot(self.action_label),
            np.asarray(self.trajectory_latent, dtype=np.float32),
        ]
        for p in (self.pose_home, self.pose_before, self.pose_after):
            if p is None:
                parts.append(np.zeros(7, dtype=np.float32))
            else:
                parts.append(np.asarray(p, dtype=np.float32)[:7])
        rel = np.array([
            1.0 if self.relation_axes.get("in") else 0.0,
            1.0 if self.relation_axes.get("on") else 0.0,
            1.0 if self.drop_flag else 0.0,
        ], dtype=np.float32)
        parts.append(rel)
        flat = np.concatenate(parts).astype(np.float32)
        out = np.zeros(dim, dtype=np.float32)
        n = min(dim, flat.shape[0])
        out[:n] = flat[:n]
        nrm = float(np.linalg.norm(out)) + 1e-8
        return out / nrm


def record_to_episode(rec: InteractionRecord) -> SpatialEpisode:
    drop = rec.action_label.lower() == "drop"
    if rec.user_correction and str(rec.user_correction.get("kind", "")).lower() == "drop":
        drop = True
    rel = {
        "in": bool(rec.container_id),
        "on": rec.container_id is None and rec.pose_home is not None,
    }
    return SpatialEpisode(
        record_id=rec.record_id,
        object_id=rec.object_id,
        room_id=rec.room_id,
        container_id=rec.container_id,
        action_label=rec.action_label,
        action_axis=_action_onehot(rec.action_label).tolist(),
        pose_home=None if rec.pose_home is None else rec.pose_home.tolist(),
        pose_before=None if rec.pose_before is None else rec.pose_before.tolist(),
        pose_after=None if rec.pose_after is None else rec.pose_after.tolist(),
        trajectory_latent=rec.trajectory_latent.tolist(),
        relation_axes=rel,
        drop_flag=drop,
        display_name=rec.display_name,
        meta={"source": "capture_interaction"},
    )


class CapturePackage:
    """OpenObjectHouseCapture/<timestamp>/ を読む。"""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.scene: dict = {}
        self.containers: dict = {}
        self.records: list[InteractionRecord] = []
        self.episodes: list[SpatialEpisode] = []
        self._load()

    def _load(self):
        scene_path = os.path.join(self.root, "Manifest", "scene.json")
        if not os.path.isfile(scene_path):
            # ルート直下も許容
            alt = os.path.join(self.root, "scene.json")
            scene_path = alt if os.path.isfile(alt) else scene_path
        if os.path.isfile(scene_path):
            with open(scene_path, encoding="utf-8") as f:
                self.scene = json.load(f)

        cpath = os.path.join(self.root, "Manifest", "containers.json")
        if os.path.isfile(cpath):
            with open(cpath, encoding="utf-8") as f:
                self.containers = json.load(f)

        raw_list = self._load_interactions()
        self.records = [InteractionRecord.from_dict(d) for d in raw_list if isinstance(d, dict)]
        # object displayName を scene から補完
        name_map = self._object_names_from_scene()
        for r in self.records:
            if not r.display_name and r.object_id in name_map:
                r.display_name = name_map[r.object_id]
        self.episodes = [record_to_episode(r) for r in self.records]

    def _load_interactions(self) -> list:
        inter_dir = os.path.join(self.root, "interactions")
        all_path = os.path.join(inter_dir, "all.json")
        if os.path.isfile(all_path):
            with open(all_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("interactions", "records", "items"):
                    if isinstance(data.get(key), list):
                        return data[key]
                return [data]
        if not os.path.isdir(inter_dir):
            return []
        out = []
        for name in sorted(os.listdir(inter_dir)):
            if name in ("all.json", "index.json") or not name.endswith(".json"):
                continue
            with open(os.path.join(inter_dir, name), encoding="utf-8") as f:
                out.append(json.load(f))
        return out

    def _object_names_from_scene(self) -> dict[str, str]:
        m = {}
        objs = self.scene.get("objects") or self.scene.get("Objects") or []
        if isinstance(objs, dict):
            objs = list(objs.values())
        for o in objs:
            if not isinstance(o, dict):
                continue
            oid = str(o.get("objectID") or o.get("id") or "")
            nm = o.get("displayName") or o.get("name")
            if oid and nm:
                m[oid] = str(nm)
        return m

    # ── 照会 API (v1 最小) ────────────────────────────────────────────────

    def objects(self) -> list[dict]:
        """登録オブジェクト一覧 (scene + records から統合)。"""
        by_id: dict[str, dict] = {}
        # scene.json を先に載せ、interaction で上書き
        objs = self.scene.get("objects") or []
        if isinstance(objs, list):
            for o in objs:
                if not isinstance(o, dict):
                    continue
                oid = str(o.get("objectID") or o.get("id") or "")
                if not oid:
                    continue
                pos = o.get("position")
                home = None
                if isinstance(pos, list) and len(pos) >= 3:
                    home = _pose_vec({"position": pos,
                                      "rotationYDegrees": o.get("rotationYDegrees", 0)})
                    home = None if home is None else home.tolist()
                parent = None
                st = o.get("state") or {}
                if isinstance(st, dict):
                    parent = st.get("clusterParent")
                by_id[oid] = {
                    "objectID": oid,
                    "displayName": o.get("displayName") or o.get("name"),
                    "containerID": parent,
                    "poseHome": home,
                    "roomID": (self.scene.get("room") or {}).get("id")
                              or (self.episodes[0].room_id if self.episodes else None),
                }
        for e in self.episodes:
            by_id.setdefault(e.object_id, {
                "objectID": e.object_id,
                "displayName": e.display_name,
                "containerID": e.container_id,
                "poseHome": e.pose_home,
                "roomID": e.room_id,
            })
            if e.display_name:
                by_id[e.object_id]["displayName"] = e.display_name
            if e.pose_home:
                by_id[e.object_id]["poseHome"] = e.pose_home
            if e.container_id:
                by_id[e.object_id]["containerID"] = e.container_id
        for oid, nm in self._object_names_from_scene().items():
            by_id.setdefault(oid, {"objectID": oid, "displayName": nm})
            by_id[oid]["displayName"] = nm
        return list(by_id.values())

    def locate(self, query: str) -> list[dict]:
        """名前部分一致 → object 候補 (登録集合内)。"""
        q = (query or "").strip().lower()
        hits = []
        for o in self.objects():
            oid = o.get("objectID") or ""
            nm = (o.get("displayName") or "").lower()
            score = 0.0
            if q and q == oid.lower():
                score = 1.0
            elif q and nm and q in nm:
                score = 0.8
            elif q and q in oid.lower():
                score = 0.5
            elif not q:
                score = 0.1
            if score > 0:
                hits.append({**o, "score": score})
        hits.sort(key=lambda x: -x["score"])
        return hits

    def return_error(self, object_id: str) -> Optional[dict]:
        """restore/return の poseAfter と poseHome の位置誤差 (m)。
        復帰レコードが無いオブジェクトは None（drop のみ等は計測対象外）。"""
        pref = [e for e in self.episodes
                if e.object_id == object_id
                and e.action_label.lower() in RETURN_LABELS
                and e.pose_home and e.pose_after]
        if not pref:
            return None
        e = pref[-1]
        home = np.asarray(e.pose_home[:3], dtype=np.float32)
        after = np.asarray(e.pose_after[:3], dtype=np.float32)
        err = float(np.linalg.norm(home - after))
        return {
            "objectID": object_id,
            "recordID": e.record_id,
            "actionLabel": e.action_label,
            "positionErrorM": err,
            "poseHome": e.pose_home,
            "poseAfter": e.pose_after,
        }

    def relations(self) -> list[dict]:
        """containerID ベースの in 関係 + containers.json / scene.contents をマージ。"""
        rels = []
        seen = set()

        def add(parent, child, source):
            if not parent or not child:
                return
            key = (parent, child, "in")
            if key in seen:
                return
            seen.add(key)
            rels.append({"type": "in", "parent": parent, "child": child, "source": source})

        for e in self.episodes:
            if e.container_id:
                add(e.container_id, e.object_id, "interaction")

        # Capture: containers.json は [{id, childObjectIDs, ...}, ...]
        raw = self.containers
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                parent = str(item.get("id") or item.get("containerID") or "")
                children = item.get("childObjectIDs") or item.get("contents") or item.get("children") or []
                if isinstance(children, list):
                    for ch in children:
                        cid = ch if isinstance(ch, str) else (
                            ch.get("objectID") or ch.get("id") if isinstance(ch, dict) else None)
                        if cid:
                            add(parent, str(cid), "containers")
        elif isinstance(raw, dict):
            items = raw.get("containers") or raw.get("relations") or raw
            if isinstance(items, list):
                for edge in items:
                    if isinstance(edge, dict) and edge.get("type") == "in":
                        add(edge.get("parent"), edge.get("child"), "containers")
                    elif isinstance(edge, dict) and edge.get("childObjectIDs"):
                        parent = str(edge.get("id") or "")
                        for ch in edge["childObjectIDs"]:
                            add(parent, str(ch), "containers")
            elif isinstance(items, dict):
                for parent, children in items.items():
                    if parent in ("containers", "relations", "version"):
                        continue
                    if not isinstance(children, list):
                        continue
                    for ch in children:
                        cid = ch if isinstance(ch, str) else (
                            ch.get("objectID") if isinstance(ch, dict) else None)
                        if cid:
                            add(str(parent), str(cid), "containers")

        # scene.json の contents / state.clusterParent
        objs = self.scene.get("objects") or []
        if isinstance(objs, list):
            for o in objs:
                if not isinstance(o, dict):
                    continue
                oid = str(o.get("id") or o.get("objectID") or "")
                for ch in o.get("contents") or []:
                    add(oid, str(ch), "scene")
                st = o.get("state") or {}
                if isinstance(st, dict) and st.get("clusterParent"):
                    add(str(st["clusterParent"]), oid, "scene")
        return rels

    def save_episodes(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        payload = {
            "format": "verantyx.spatial_episodes",
            "version": 1,
            "source": self.root,
            "count": len(self.episodes),
            "episodes": [asdict(e) for e in self.episodes],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


# ── 永続ストア + 短い指示パース (LLMフルFTなし) ─────────────────────────────

SPATIAL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono", "spatial")


def parse_spatial_intent(text: str) -> dict:
    """日本語/英語の短い指示 → {intent, query}。言語モデルは使わない。"""
    t = (text or "").strip()
    low = t.lower()
    if low in ("list", "一覧", "objects", "物一覧"):
        return {"intent": "list", "query": ""}
    for pref in ("戻して", "元に戻", "もどして", "restore", "return ", "put back", "putback"):
        if pref in low or pref in t:
            q = t
            for p in ("を戻して", "を元に戻して", "戻して", "元に戻して",
                      "restore", "return", "put back", "putback"):
                q = q.replace(p, " ")
            return {"intent": "return", "query": q.strip(" 　") or t}
    for pref in ("出して", "取り出", "抜いて", "extract", "take out"):
        if pref in low or pref in t:
            return {"intent": "extract", "query": t}
    m = re.search(r"(.+?)(?:は|の)?\s*どこ", t)
    if m or "where" in low or "locate" in low or "find " in low:
        q = m.group(1).strip() if m else t
        for p in ("where is", "where's", "find", "locate", "？", "?"):
            q = re.sub(re.escape(p), " ", q, flags=re.I)
        return {"intent": "locate", "query": q.strip(" 　") or t}
    return {"intent": "locate", "query": t}


class SpatialStore:
    """Capture パッケージを取り込み、Locate/Return を永続照会する受け皿。"""

    def __init__(self, root: Optional[str] = None):
        self.root = os.path.abspath(root or SPATIAL_DIR)
        self.packages_dir = os.path.join(self.root, "packages")
        self.index_path = os.path.join(self.root, "index.json")
        os.makedirs(self.packages_dir, exist_ok=True)
        self.index = self._load_index()
        self._active: Optional[CapturePackage] = None
        self._active_id: Optional[str] = None
        if self.index.get("active"):
            try:
                self.load(self.index["active"])
            except Exception:
                pass

    def _load_index(self) -> dict:
        if os.path.isfile(self.index_path):
            with open(self.index_path, encoding="utf-8") as f:
                return json.load(f)
        return {"version": 1, "active": None, "packages": []}

    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def ingest(self, package_path: str, name: Optional[str] = None) -> str:
        """OpenObjectHouseCapture/<timestamp>/ をストアに取り込み active にする。"""
        pkg = CapturePackage(package_path)
        stamp = name or os.path.basename(os.path.abspath(package_path).rstrip("/"))
        dest = os.path.join(self.packages_dir, stamp)
        os.makedirs(dest, exist_ok=True)
        # メタのみコピーせず、元パスを参照 + episodes を永続化
        meta = {
            "id": stamp,
            "source": os.path.abspath(package_path),
            "ingestedAt": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
            "records": len(pkg.records),
            "objects": len(pkg.objects()),
            "episodesFile": os.path.join(dest, "spatial_episodes.json"),
        }
        pkg.save_episodes(meta["episodesFile"])
        with open(os.path.join(dest, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        # index 更新
        self.index["packages"] = [p for p in self.index.get("packages", [])
                                  if p.get("id") != stamp]
        self.index["packages"].append(meta)
        self.index["active"] = stamp
        self._save_index()
        self._active = pkg
        self._active_id = stamp
        return stamp

    def load(self, package_id: str) -> CapturePackage:
        entry = next((p for p in self.index.get("packages", [])
                      if p.get("id") == package_id), None)
        if not entry:
            raise FileNotFoundError(f"unknown package id: {package_id}")
        src = entry.get("source")
        if not src or not os.path.isdir(src):
            raise FileNotFoundError(f"source missing: {src}")
        self._active = CapturePackage(src)
        self._active_id = package_id
        self.index["active"] = package_id
        self._save_index()
        return self._active

    @property
    def pkg(self) -> Optional[CapturePackage]:
        return self._active

    def status(self) -> dict:
        return {
            "root": self.root,
            "active": self._active_id,
            "packages": [
                {"id": p.get("id"), "records": p.get("records"),
                 "objects": p.get("objects"), "source": p.get("source")}
                for p in self.index.get("packages", [])
            ],
        }

    def handle(self, text: str) -> dict:
        """短い指示を処理。戻り値は表示用 dict。"""
        if self._active is None:
            return {"ok": False, "error": "パッケージ未読込。/spatial ingest <path> を先に実行"}
        intent = parse_spatial_intent(text)
        kind = intent["intent"]
        q = intent["query"]
        if kind == "list":
            return {"ok": True, "intent": kind, "objects": self._active.objects()}
        if kind == "locate":
            hits = self._active.locate(q)
            return {"ok": True, "intent": kind, "query": q, "hits": hits[:5]}
        if kind == "return":
            hits = self._active.locate(q)
            if not hits:
                return {"ok": False, "intent": kind, "query": q, "error": "object not found"}
            oid = hits[0]["objectID"]
            err = self._active.return_error(oid)
            return {
                "ok": True, "intent": kind, "query": q, "objectID": oid,
                "displayName": hits[0].get("displayName"),
                "returnError": err,
                "poseHome": hits[0].get("poseHome"),
                "hint": "Capture/Play 側で poseHome へ誘導。こちらは誤差と目標ポーズのみ返す。",
            }
        if kind == "extract":
            hits = self._active.locate(q)
            return {
                "ok": True, "intent": kind, "query": q,
                "hits": hits[:3],
                "relations": [r for r in self._active.relations()
                              if hits and (r.get("child") == hits[0]["objectID"]
                                           or r.get("parent") == hits[0]["objectID"])],
            }
        return {"ok": False, "error": f"unknown intent {kind}"}


def main():
    ap = argparse.ArgumentParser(description="Capture パッケージ → SpatialEpisode / SpatialStore")
    sub = ap.add_subparsers(dest="cmd")

    p_imp = sub.add_parser("import", help="パッケージを SpatialEpisode 化")
    p_imp.add_argument("package", help="OpenObjectHouseCapture/<timestamp> ディレクトリ")
    p_imp.add_argument("--out", default="", help="episodes.json の出力先")
    p_imp.add_argument("--locate", default="", help="Locate クエリ")

    p_ing = sub.add_parser("ingest", help="永続ストアへ取り込み")
    p_ing.add_argument("package")
    p_ing.add_argument("--name", default="")

    p_ask = sub.add_parser("ask", help="短い指示 (どこ？/戻して)")
    p_ask.add_argument("text")
    p_ask.add_argument("--store", default="", help="SpatialStore ルート")

    p_st = sub.add_parser("status", help="ストア状態")
    p_st.add_argument("--store", default="")

    # 後方互換: 引数がディレクトリだけなら import
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("-") and sys.argv[1] not in (
            "import", "ingest", "ask", "status"):
        if os.path.isdir(sys.argv[1]):
            sys.argv.insert(1, "import")

    args = ap.parse_args()
    if args.cmd == "import" or args.cmd is None:
        if args.cmd is None:
            ap.print_help()
            return
        pkg = CapturePackage(args.package)
        print(f"[spatial] records={len(pkg.records)} episodes={len(pkg.episodes)} "
              f"objects={len(pkg.objects())}")
        if args.locate:
            for h in pkg.locate(args.locate)[:5]:
                print(f"  locate: {h.get('displayName') or h['objectID']} "
                      f"score={h['score']:.2f} home={h.get('poseHome')}")
        out = args.out or os.path.join(args.package, "spatial_episodes.json")
        pkg.save_episodes(out)
        print(f"[spatial] wrote {out}")
    elif args.cmd == "ingest":
        store = SpatialStore()
        pid = store.ingest(args.package, name=args.name or None)
        print(f"[spatial] ingested id={pid} active objects={len(store.pkg.objects())}")
    elif args.cmd == "ask":
        store = SpatialStore(args.store or None)
        print(json.dumps(store.handle(args.text), ensure_ascii=False, indent=2))
    elif args.cmd == "status":
        store = SpatialStore(args.store or None)
        print(json.dumps(store.status(), ensure_ascii=False, indent=2))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
