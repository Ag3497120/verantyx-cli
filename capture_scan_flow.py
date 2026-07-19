"""
capture_scan_flow.py — Capture 精度レンジ切替フロー (ピンチ廃止 → 掴み / LiDAR / 視線)
==============================================================================

旧フローの問題:
  - 片手で物を持ち、もう片手でピンチして小物モードへ切替 → 両手操作が潰れる
  - 本棚から取り出した小物でレンジが切り替わらず精度低下
  - 小物スキャン時に背景がメッシュにくっつく / 切り出し失敗

新フロー:
  1. 既定は room_full（部屋を歩きながらフルスキャン）
  2. 指と物体の接触で「掴み」を検出 → 候補リング表示（ピンチ不要）
  3. 両手掴み = 大物（棚・モニタ等）。片手 = 小〜中
  4. 近接時は LiDAR 距離で close_range へ自動切替（小物精度用）
  5. 視線ポインタを候補に 3 秒 dwell で精密撮影開始（対応関係・位置関係の確定）
  6. 撮影中は指見つめメニューを Digital Crown までロック
  7. close_range では背景カットアウト必須

本モジュールは Capture (open-object-house) 実装の契約ロジックと、
Verantyx 側での検証・エクスポート正規化に使う。実機 ARKit 呼び出しは含まない。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


# ── 閾値（Capture と共有。実機でキャリブ可能） ─────────────────────────────

GAZE_DWELL_SEC = 3.0
# この距離未満に近づいたら精密モード候補
CLOSE_RANGE_LIDAR_M = 0.55
# AABB 最長辺がこれ未満なら小物
SMALL_OBJECT_MAX_EXTENT_M = 0.35
MEDIUM_OBJECT_MAX_EXTENT_M = 0.90
# 指先〜メッシュ表面の接触判定
FINGER_CONTACT_EPS_M = 0.018
# 掴み成立に必要な接触指本数（親指含む）
MIN_CONTACT_FINGERS = 2


class ScanMode(str, Enum):
    ROOM_FULL = "room_full"
    OBJECT_CANDIDATE = "object_candidate"
    CLOSE_RANGE = "close_range"
    LARGE_OBJECT = "large_object"


class SizeClass(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class FingerId(str, Enum):
    THUMB = "thumb"
    INDEX = "index"
    MIDDLE = "middle"
    RING = "ring"
    LITTLE = "little"


@dataclass
class ScanProfile:
    """メッシュ／LiDAR のレンジと切り出し設定。"""
    mode: str
    lidar_focus_m: float
    voxel_size_m: float
    isolate_foreground: bool
    max_background_depth_m: Optional[float]
    allow_hand_occlusion: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# モード別プロファイル（旧「レンジ切替失敗」をここで強制）
PROFILES: dict[str, ScanProfile] = {
    ScanMode.ROOM_FULL.value: ScanProfile(
        mode=ScanMode.ROOM_FULL.value,
        lidar_focus_m=4.0,
        voxel_size_m=0.02,
        isolate_foreground=False,
        max_background_depth_m=None,
    ),
    ScanMode.OBJECT_CANDIDATE.value: ScanProfile(
        mode=ScanMode.OBJECT_CANDIDATE.value,
        lidar_focus_m=1.5,
        voxel_size_m=0.012,
        isolate_foreground=False,
        max_background_depth_m=None,
    ),
    ScanMode.CLOSE_RANGE.value: ScanProfile(
        mode=ScanMode.CLOSE_RANGE.value,
        lidar_focus_m=0.55,
        voxel_size_m=0.004,
        isolate_foreground=True,
        max_background_depth_m=0.75,
    ),
    ScanMode.LARGE_OBJECT.value: ScanProfile(
        mode=ScanMode.LARGE_OBJECT.value,
        lidar_focus_m=2.2,
        voxel_size_m=0.01,
        isolate_foreground=False,
        max_background_depth_m=None,
    ),
}


@dataclass
class GraspObservation:
    """1 フレーム分の掴み観測。ピンチ UI は使わない。"""
    hands_used: int  # 1 or 2
    contact_fingers: list[str]  # FingerId values touching the object
    finger_object_distances_m: dict[str, float] = field(default_factory=dict)
    lidar_distance_m: Optional[float] = None
    object_extent_m: Optional[float] = None  # AABB longest edge
    object_accel_mps2: Optional[float] = None  # 初動（持ち上げ加速度）
    tip_stiffness_proxy: Optional[float] = None  # 0..1 指の強張り近似
    pinch_gesture: bool = False  # 旧フロー互換。新フローではモード切替に使わない

    def contacting(self) -> bool:
        contacts = [
            f for f, d in self.finger_object_distances_m.items()
            if d <= FINGER_CONTACT_EPS_M
        ]
        # distances が無い場合は contact_fingers を信頼
        fingers = contacts or list(self.contact_fingers)
        return len(set(fingers)) >= MIN_CONTACT_FINGERS


@dataclass
class WeightEstimate:
    """人間の無意識の重さ見積もりを、掴み方から近似記録する。"""
    finger_count: int
    fingers: list[str]
    hands_used: int
    size_class: str
    mass_proxy_kg: float
    confidence: float
    cues: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "fingerCount": self.finger_count,
            "fingers": list(self.fingers),
            "handsUsed": self.hands_used,
            "sizeClass": self.size_class,
            "massProxyKg": self.mass_proxy_kg,
            "confidence": self.confidence,
            "cues": dict(self.cues),
        }


@dataclass
class CandidateObject:
    object_id: str
    display_name: Optional[str] = None
    ring_center: Optional[list[float]] = None
    ring_radius_m: float = 0.08
    container_id: Optional[str] = None
    relation: Optional[str] = None  # in / on / free


@dataclass
class ScanCaptureMeta:
    """InteractionRecord.scanCapture に載せる正規化メタ。"""
    schema_version: int
    mode: str
    size_class: str
    profile: dict
    grasp: dict
    weight: dict
    gaze_confirmed: bool
    gaze_dwell_sec: float
    menu_locked: bool
    isolation_applied: bool
    trigger: str  # "grasp_contact" | never "pinch_toggle"
    selected_object_id: Optional[str] = None
    container_id: Optional[str] = None
    relation: Optional[str] = None
    candidate_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            "mode": self.mode,
            "sizeClass": self.size_class,
            "profile": dict(self.profile),
            "grasp": dict(self.grasp),
            "weight": dict(self.weight),
            "gazeConfirmed": self.gaze_confirmed,
            "gazeDwellSec": self.gaze_dwell_sec,
            "menuLocked": self.menu_locked,
            "isolationApplied": self.isolation_applied,
            "trigger": self.trigger,
            "selectedObjectID": self.selected_object_id,
            "containerID": self.container_id,
            "relation": self.relation,
            "candidateIDs": list(self.candidate_ids),
        }


def classify_size(
    hands_used: int,
    object_extent_m: Optional[float],
    lidar_distance_m: Optional[float],
) -> SizeClass:
    """両手 = 大物。片手は AABB / LiDAR で small|medium。"""
    if hands_used >= 2:
        return SizeClass.LARGE
    extent = object_extent_m
    if extent is None and lidar_distance_m is not None:
        # 近接ほど小物寄り（粗いヒューリスティック）
        extent = 0.20 if lidar_distance_m < CLOSE_RANGE_LIDAR_M else 0.50
    if extent is None:
        return SizeClass.MEDIUM
    if extent <= SMALL_OBJECT_MAX_EXTENT_M:
        return SizeClass.SMALL
    if extent <= MEDIUM_OBJECT_MAX_EXTENT_M:
        return SizeClass.MEDIUM
    return SizeClass.LARGE


def estimate_weight(obs: GraspObservation, size_class: SizeClass) -> WeightEstimate:
    """
    指本数を主信号に、初動加速度・指強張りを加算して mass_proxy を出す。
    絶対 kg ではなく、ゲーム物理／操作学習用の相対プロキシ。
    """
    fingers = sorted(set(obs.contact_fingers))
    # 親指を含む接触を優先カウント
    n = len(fingers)
    if n == 0:
        n = MIN_CONTACT_FINGERS

    # ベース: 指が多いほど重い想定（無意識の握り分け）
    base = {2: 0.15, 3: 0.40, 4: 0.80, 5: 1.40}.get(min(n, 5), 0.15)
    if obs.hands_used >= 2:
        base *= 3.5

    cues: dict[str, Any] = {"finger_count_base_kg": base}

    if obs.object_accel_mps2 is not None:
        # 初動が遅い → 重い側へ（簡易）
        accel = max(0.05, float(obs.object_accel_mps2))
        accel_factor = min(2.5, 1.2 / accel)
        base *= accel_factor
        cues["accel_mps2"] = accel
        cues["accel_factor"] = accel_factor

    if obs.tip_stiffness_proxy is not None:
        stiff = max(0.0, min(1.0, float(obs.tip_stiffness_proxy)))
        stiff_boost = 1.0 + 0.6 * stiff
        base *= stiff_boost
        cues["tip_stiffness_proxy"] = stiff
        cues["stiffness_factor"] = stiff_boost

    size_scale = {
        SizeClass.SMALL: 0.7,
        SizeClass.MEDIUM: 1.0,
        SizeClass.LARGE: 1.8,
    }[size_class]
    mass = max(0.02, base * size_scale)
    cues["size_scale"] = size_scale

    conf = 0.45
    if n >= 3:
        conf += 0.15
    if obs.object_accel_mps2 is not None:
        conf += 0.15
    if obs.tip_stiffness_proxy is not None:
        conf += 0.10
    if obs.hands_used >= 2:
        conf += 0.10
    conf = min(0.95, conf)

    return WeightEstimate(
        finger_count=n,
        fingers=fingers,
        hands_used=obs.hands_used,
        size_class=size_class.value,
        mass_proxy_kg=round(mass, 4),
        confidence=round(conf, 3),
        cues=cues,
    )


def select_mode(size_class: SizeClass, lidar_distance_m: Optional[float],
                capturing: bool) -> ScanMode:
    """サイズと距離から精度レンジを選ぶ。小物の近接は必ず close_range。"""
    if size_class == SizeClass.LARGE:
        return ScanMode.LARGE_OBJECT
    if capturing and size_class == SizeClass.SMALL:
        return ScanMode.CLOSE_RANGE
    if lidar_distance_m is not None and lidar_distance_m <= CLOSE_RANGE_LIDAR_M:
        if size_class in (SizeClass.SMALL, SizeClass.MEDIUM):
            return ScanMode.CLOSE_RANGE if capturing else ScanMode.OBJECT_CANDIDATE
    if capturing:
        return ScanMode.CLOSE_RANGE if size_class == SizeClass.SMALL else ScanMode.OBJECT_CANDIDATE
    return ScanMode.OBJECT_CANDIDATE


def profile_for(mode: ScanMode) -> ScanProfile:
    return PROFILES[mode.value]


def should_isolate(mode: ScanMode) -> bool:
    """小物精密時は背景削除を必須にする（旧バグの再発防止）。"""
    return profile_for(mode).isolate_foreground


@dataclass
class FlowState:
    mode: ScanMode = ScanMode.ROOM_FULL
    size_class: SizeClass = SizeClass.MEDIUM
    menu_locked: bool = False
    gaze_target_id: Optional[str] = None
    gaze_dwell_sec: float = 0.0
    capturing: bool = False
    selected_object_id: Optional[str] = None
    container_id: Optional[str] = None
    relation: Optional[str] = None
    candidates: list[CandidateObject] = field(default_factory=list)
    last_weight: Optional[WeightEstimate] = None
    last_grasp: Optional[GraspObservation] = None

    def profile(self) -> ScanProfile:
        return profile_for(self.mode)


class CaptureScanFlow:
    """
    ピンチトグルを廃したスキャン状態機械。

    典型シーケンス:
      room_full
        → (grasp contact) object_candidate + rings
        → (gaze dwell 3s) close_range|large_object capturing, menu locked
        → (release or done) room_full, menu unlock via crown if still locked
    """

    def __init__(self, gaze_dwell_sec: float = GAZE_DWELL_SEC):
        self.gaze_dwell_needed = float(gaze_dwell_sec)
        self.state = FlowState()

    # ── イベント ──────────────────────────────────────────────────────────

    def on_grasp(self, obs: GraspObservation,
                 candidates: Optional[list[CandidateObject]] = None) -> FlowState:
        """指−物体接触で掴み開始。pinch_gesture は無視（モード切替しない）。"""
        if obs.pinch_gesture and not obs.contacting():
            # 旧フロー互換: ピンチだけでは精度モードに入らない
            return self.state
        if not obs.contacting():
            return self.state

        size = classify_size(obs.hands_used, obs.object_extent_m, obs.lidar_distance_m)
        weight = estimate_weight(obs, size)
        mode = select_mode(size, obs.lidar_distance_m, capturing=False)

        self.state.size_class = size
        self.state.last_grasp = obs
        self.state.last_weight = weight
        self.state.mode = mode
        self.state.capturing = False
        self.state.gaze_dwell_sec = 0.0
        if candidates is not None:
            self.state.candidates = list(candidates)
        return self.state

    def on_candidates(self, candidates: list[CandidateObject]) -> FlowState:
        """掴み周囲のスキャン画像から「これ？」リング候補を更新。"""
        self.state.candidates = list(candidates)
        if self.state.mode == ScanMode.ROOM_FULL and candidates:
            self.state.mode = ScanMode.OBJECT_CANDIDATE
        return self.state

    def on_gaze(self, object_id: Optional[str], dt_sec: float) -> FlowState:
        """視線ポインタ。同一候補へ累積 dwell。3 秒で精密撮影開始。"""
        if self.state.capturing:
            return self.state
        if not object_id or object_id not in {c.object_id for c in self.state.candidates}:
            self.state.gaze_target_id = None
            self.state.gaze_dwell_sec = 0.0
            return self.state

        if object_id != self.state.gaze_target_id:
            self.state.gaze_target_id = object_id
            self.state.gaze_dwell_sec = 0.0

        self.state.gaze_dwell_sec += max(0.0, float(dt_sec))
        if self.state.gaze_dwell_sec >= self.gaze_dwell_needed:
            self._begin_capture(object_id)
        return self.state

    def on_lidar_distance(self, distance_m: float) -> FlowState:
        """近接で小物レンジへ寄せる。本棚取り出し後の精度低下対策。"""
        if self.state.last_grasp is not None:
            self.state.last_grasp.lidar_distance_m = float(distance_m)
            self.state.size_class = classify_size(
                self.state.last_grasp.hands_used,
                self.state.last_grasp.object_extent_m,
                distance_m,
            )
        if self.state.capturing:
            self.state.mode = select_mode(
                self.state.size_class, distance_m, capturing=True)
        elif self.state.mode != ScanMode.ROOM_FULL:
            self.state.mode = select_mode(
                self.state.size_class, distance_m, capturing=False)
        return self.state

    def on_release(self) -> FlowState:
        """手放し。撮影中ならセッション終了して room_full へ。メニューは Crown 待ち可。"""
        was_capturing = self.state.capturing
        self.state.capturing = False
        self.state.gaze_dwell_sec = 0.0
        self.state.gaze_target_id = None
        self.state.candidates = []
        self.state.mode = ScanMode.ROOM_FULL
        if was_capturing:
            # 撮影中ロックは Crown まで維持（誤メニュー防止）
            self.state.menu_locked = True
        else:
            self.state.menu_locked = False
        return self.state

    def on_digital_crown(self) -> FlowState:
        """Digital Crown で指見つめメニューロック解除。"""
        self.state.menu_locked = False
        return self.state

    def finger_menu_allowed(self) -> bool:
        return not self.state.menu_locked

    # ── 出力 ─────────────────────────────────────────────────────────────

    def build_scan_capture_meta(self) -> ScanCaptureMeta:
        st = self.state
        prof = st.profile()
        grasp = st.last_grasp
        weight = st.last_weight or WeightEstimate(
            finger_count=0, fingers=[], hands_used=0,
            size_class=st.size_class.value, mass_proxy_kg=0.0,
            confidence=0.0, cues={},
        )
        grasp_dict = {
            "handsUsed": grasp.hands_used if grasp else 0,
            "contactFingers": list(grasp.contact_fingers) if grasp else [],
            "fingerObjectDistancesM": dict(grasp.finger_object_distances_m) if grasp else {},
            "lidarDistanceM": grasp.lidar_distance_m if grasp else None,
            "objectExtentM": grasp.object_extent_m if grasp else None,
            "objectAccelMps2": grasp.object_accel_mps2 if grasp else None,
            "tipStiffnessProxy": grasp.tip_stiffness_proxy if grasp else None,
            "pinchIgnoredForModeSwitch": True,
        }
        return ScanCaptureMeta(
            schema_version=2,
            mode=st.mode.value,
            size_class=st.size_class.value,
            profile=prof.to_dict(),
            grasp=grasp_dict,
            weight=weight.to_dict(),
            gaze_confirmed=bool(st.selected_object_id and st.capturing),
            gaze_dwell_sec=round(st.gaze_dwell_sec, 3),
            menu_locked=st.menu_locked,
            isolation_applied=should_isolate(st.mode) and st.capturing,
            trigger="grasp_contact",
            selected_object_id=st.selected_object_id,
            container_id=st.container_id,
            relation=st.relation,
            candidate_ids=[c.object_id for c in st.candidates],
        )

    def assert_precision_invariants(self) -> list[str]:
        """旧バグ再発チェック。空なら OK。"""
        errors: list[str] = []
        st = self.state
        if st.capturing and st.size_class == SizeClass.SMALL:
            if st.mode != ScanMode.CLOSE_RANGE:
                errors.append("small object capture must use close_range")
            if not should_isolate(st.mode):
                errors.append("small object capture must isolate foreground")
            if st.profile().lidar_focus_m > CLOSE_RANGE_LIDAR_M + 1e-6:
                errors.append("close_range lidar focus too wide for small object")
        if st.capturing and not st.menu_locked:
            errors.append("menu must be locked while capturing")
        if st.mode == ScanMode.CLOSE_RANGE and st.capturing and not st.profile().isolate_foreground:
            errors.append("close_range profile missing isolation")
        return errors

    # ── internal ─────────────────────────────────────────────────────────

    def _begin_capture(self, object_id: str) -> None:
        cand = next((c for c in self.state.candidates if c.object_id == object_id), None)
        lidar = self.state.last_grasp.lidar_distance_m if self.state.last_grasp else None
        self.state.selected_object_id = object_id
        self.state.container_id = cand.container_id if cand else None
        self.state.relation = cand.relation if cand else None
        self.state.capturing = True
        self.state.menu_locked = True
        self.state.mode = select_mode(self.state.size_class, lidar, capturing=True)


def normalize_scan_capture(raw: Optional[dict]) -> Optional[dict]:
    """InteractionRecord.scanCapture / scan_capture を v2 形に寄せる。"""
    if not isinstance(raw, dict):
        return None
    mode = raw.get("mode") or raw.get("scanMode") or ScanMode.ROOM_FULL.value
    size = raw.get("sizeClass") or raw.get("size_class") or SizeClass.MEDIUM.value
    profile = raw.get("profile")
    if not isinstance(profile, dict):
        try:
            profile = profile_for(ScanMode(mode)).to_dict()
        except ValueError:
            profile = PROFILES[ScanMode.ROOM_FULL.value].to_dict()
    weight = raw.get("weight") or raw.get("weightEstimate") or {}
    grasp = raw.get("grasp") or raw.get("graspObservation") or {}
    return {
        "schemaVersion": int(raw.get("schemaVersion") or raw.get("schema_version") or 2),
        "mode": mode,
        "sizeClass": size,
        "profile": profile,
        "grasp": grasp,
        "weight": weight,
        "gazeConfirmed": bool(raw.get("gazeConfirmed") or raw.get("gaze_confirmed")),
        "gazeDwellSec": float(raw.get("gazeDwellSec") or raw.get("gaze_dwell_sec") or 0),
        "menuLocked": bool(raw.get("menuLocked") if "menuLocked" in raw
                           else raw.get("menu_locked", False)),
        "isolationApplied": bool(raw.get("isolationApplied")
                                 if "isolationApplied" in raw
                                 else raw.get("isolation_applied", False)),
        "trigger": raw.get("trigger") or "grasp_contact",
        "selectedObjectID": raw.get("selectedObjectID") or raw.get("selected_object_id"),
        "containerID": raw.get("containerID") or raw.get("container_id"),
        "relation": raw.get("relation"),
        "candidateIDs": list(raw.get("candidateIDs") or raw.get("candidate_ids") or []),
    }


__all__ = [
    "GAZE_DWELL_SEC",
    "CLOSE_RANGE_LIDAR_M",
    "ScanMode",
    "SizeClass",
    "FingerId",
    "ScanProfile",
    "GraspObservation",
    "WeightEstimate",
    "CandidateObject",
    "ScanCaptureMeta",
    "FlowState",
    "CaptureScanFlow",
    "classify_size",
    "estimate_weight",
    "select_mode",
    "profile_for",
    "should_isolate",
    "normalize_scan_capture",
    "PROFILES",
]
