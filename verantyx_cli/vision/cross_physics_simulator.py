#!/usr/bin/env python3
"""
Cross Physics Simulator
Cross構造物理シミュレータ

物理法則をCross構造上でシミュレーションし、
世界の真理を学習するためのエンジン。

重力、慣性、衝突などの法則を適用し、
時系列Cross構造を生成する。
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import copy
from datetime import datetime

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


@dataclass
class PhysicsPoint:
    """物理シミュレーション用のCross点"""
    # 位置（3D空間）
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # 速度（3D空間）
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    velocity_z: float = 0.0

    # Cross 6軸の値
    front: float = 0.5
    back: float = 0.5
    up: float = 0.5
    down: float = 0.5
    right: float = 0.5
    left: float = 0.5

    # Cross 6軸の速度
    velocity_front: float = 0.0
    velocity_back: float = 0.0
    velocity_up: float = 0.0
    velocity_down: float = 0.0
    velocity_right: float = 0.0
    velocity_left: float = 0.0

    # 物理属性
    mass: float = 1.0
    radius: float = 0.1

    def update_cross_axes(self):
        """3D座標からCross軸の値を更新"""
        # [-1, 1] → [0, 1]
        self.right = (self.x + 1) / 2
        self.left = 1.0 - self.right

        self.up = (self.y + 1) / 2
        self.down = 1.0 - self.up

        self.front = (self.z + 1) / 2
        self.back = 1.0 - self.front


class CrossPhysicsLaw:
    """Cross構造における物理法則の基底クラス"""

    def __init__(self, name: str):
        self.name = name

    def apply(self, point: PhysicsPoint, dt: float) -> PhysicsPoint:
        """
        物理法則を点に適用

        Args:
            point: 物理点
            dt: 時間刻み

        Returns:
            更新された点
        """
        raise NotImplementedError

    def apply_multi(
        self,
        points: List[PhysicsPoint],
        dt: float
    ) -> List[PhysicsPoint]:
        """
        複数の点に物理法則を適用

        Args:
            points: 物理点のリスト
            dt: 時間刻み

        Returns:
            更新された点のリスト
        """
        return [self.apply(p, dt) for p in points]


class GravityLaw(CrossPhysicsLaw):
    """重力法則"""

    def __init__(self, gravity: float = 9.8):
        super().__init__("Gravity")
        self.gravity = gravity

    def apply(self, point: PhysicsPoint, dt: float) -> PhysicsPoint:
        """
        重力を適用

        DOWN軸方向に加速度を与える
        """
        # Y方向の速度を更新（下方向 = 負）
        point.velocity_y -= self.gravity * dt

        # DOWN軸の速度を更新
        point.velocity_down = abs(point.velocity_y) if point.velocity_y < 0 else 0

        return point


class InertiaLaw(CrossPhysicsLaw):
    """慣性法則"""

    def __init__(self):
        super().__init__("Inertia")

    def apply(self, point: PhysicsPoint, dt: float) -> PhysicsPoint:
        """
        慣性を適用

        現在の速度で等速運動
        """
        # 位置を更新
        point.x += point.velocity_x * dt
        point.y += point.velocity_y * dt
        point.z += point.velocity_z * dt

        # Cross軸を更新
        point.update_cross_axes()

        return point


class CollisionLaw(CrossPhysicsLaw):
    """衝突法則（地面との衝突）"""

    def __init__(self, ground_y: float = -1.0, restitution: float = 0.8):
        super().__init__("Collision")
        self.ground_y = ground_y  # 地面のY座標
        self.restitution = restitution  # 反発係数

    def apply(self, point: PhysicsPoint, dt: float) -> PhysicsPoint:
        """
        地面との衝突を処理
        """
        # 地面に到達したか？
        if point.y <= self.ground_y and point.velocity_y < 0:
            # 地面に配置
            point.y = self.ground_y

            # 跳ね返り
            point.velocity_y = -point.velocity_y * self.restitution

            # 速度が小さければ停止
            if abs(point.velocity_y) < 0.1:
                point.velocity_y = 0

        return point


class FrictionLaw(CrossPhysicsLaw):
    """摩擦法則"""

    def __init__(self, friction: float = 0.95):
        super().__init__("Friction")
        self.friction = friction  # 摩擦係数（0.95 = 5%減速）

    def apply(self, point: PhysicsPoint, dt: float) -> PhysicsPoint:
        """
        摩擦を適用

        速度を徐々に減少させる
        """
        point.velocity_x *= self.friction
        point.velocity_y *= self.friction
        point.velocity_z *= self.friction

        return point


class BoundaryLaw(CrossPhysicsLaw):
    """境界法則（空間の端での反射）"""

    def __init__(self, min_x: float = -1.0, max_x: float = 1.0):
        super().__init__("Boundary")
        self.min_x = min_x
        self.max_x = max_x

    def apply(self, point: PhysicsPoint, dt: float) -> PhysicsPoint:
        """
        境界での反射を処理
        """
        # X軸の境界
        if point.x < self.min_x:
            point.x = self.min_x
            point.velocity_x = -point.velocity_x * 0.8

        if point.x > self.max_x:
            point.x = self.max_x
            point.velocity_x = -point.velocity_x * 0.8

        return point


class CrossPhysicsSimulator:
    """Cross構造物理シミュレータ"""

    def __init__(self, dt: float = 0.016):
        """
        Initialize physics simulator

        Args:
            dt: 時間刻み（デフォルト: 0.016秒 = 60 FPS）
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required. Install with: pip install numpy")

        self.dt = dt
        self.laws: List[CrossPhysicsLaw] = []
        self.time = 0.0

    def add_law(self, law: CrossPhysicsLaw):
        """物理法則を追加"""
        self.laws.append(law)
        print(f"  📐 物理法則を追加: {law.name}")

    def simulate(
        self,
        initial_points: List[PhysicsPoint],
        duration: float,
        record_interval: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        物理シミュレーションを実行

        Args:
            initial_points: 初期点群
            duration: シミュレーション時間（秒）
            record_interval: 記録間隔（Noneの場合は毎フレーム）

        Returns:
            時系列Cross構造のリスト
        """
        print(f"\n⚡ 物理シミュレーション開始")
        print(f"   期間: {duration}秒")
        print(f"   時間刻み: {self.dt}秒")
        print(f"   物理法則数: {len(self.laws)}")
        print()

        # 点をコピー
        points = [copy.deepcopy(p) for p in initial_points]

        # 時系列記録
        timeline = []

        # ステップ数を計算
        num_steps = int(duration / self.dt)

        # 記録間隔（フレーム数）
        if record_interval is None:
            record_every = 1
        else:
            record_every = max(1, int(record_interval / self.dt))

        self.time = 0.0

        for step in range(num_steps):
            # 各物理法則を適用
            for law in self.laws:
                points = law.apply_multi(points, self.dt)

            # 記録するか？
            if step % record_every == 0:
                # 現在の状態を記録
                snapshot = {
                    "time": self.time,
                    "step": step,
                    "points": [self._point_to_dict(p) for p in points],
                    "cross_structure": self._to_cross_structure(points)
                }

                timeline.append(snapshot)

            self.time += self.dt

            # 進捗表示（10%ごと）
            if step % (num_steps // 10) == 0:
                progress = (step / num_steps) * 100
                print(f"   進捗: {progress:.0f}%")

        print(f"   ✅ シミュレーション完了（{len(timeline)} フレーム記録）")
        print()

        return timeline

    def _point_to_dict(self, point: PhysicsPoint) -> Dict[str, Any]:
        """物理点を辞書に変換"""
        return {
            "position": {"x": point.x, "y": point.y, "z": point.z},
            "velocity": {
                "x": point.velocity_x,
                "y": point.velocity_y,
                "z": point.velocity_z
            },
            "cross_axes": {
                "FRONT": point.front,
                "BACK": point.back,
                "UP": point.up,
                "DOWN": point.down,
                "RIGHT": point.right,
                "LEFT": point.left
            }
        }

    def _to_cross_structure(self, points: List[PhysicsPoint]) -> Dict[str, Any]:
        """点群をCross構造に変換"""
        if not points:
            return {}

        # 各軸の統計を計算
        axes_stats = {}

        for axis_name in ["FRONT", "BACK", "UP", "DOWN", "RIGHT", "LEFT"]:
            values = [getattr(p, axis_name.lower()) for p in points]

            axes_stats[axis_name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values))
            }

        return {
            "num_points": len(points),
            "axes": axes_stats,
            "center_of_mass": {
                "x": float(np.mean([p.x for p in points])),
                "y": float(np.mean([p.y for p in points])),
                "z": float(np.mean([p.z for p in points]))
            }
        }


def create_falling_ball_simulation(
    duration: float = 2.0,
    initial_height: float = 1.0,
    gravity: float = 9.8,
    restitution: float = 0.8
) -> List[Dict[str, Any]]:
    """
    落下する球のシミュレーションを作成

    Args:
        duration: シミュレーション時間（秒）
        initial_height: 初期高さ
        gravity: 重力加速度
        restitution: 反発係数

    Returns:
        時系列Cross構造
    """
    print("\n" + "=" * 60)
    print("🏀 落下シミュレーション")
    print("=" * 60)

    # 物理シミュレータを作成
    simulator = CrossPhysicsSimulator(dt=0.016)

    # 物理法則を追加
    simulator.add_law(GravityLaw(gravity=gravity))
    simulator.add_law(InertiaLaw())
    simulator.add_law(CollisionLaw(ground_y=-1.0, restitution=restitution))

    # 初期状態: 空中の球
    ball = PhysicsPoint(
        x=0.0,
        y=initial_height,
        z=0.0,
        velocity_x=0.0,
        velocity_y=0.0,
        velocity_z=0.0
    )
    ball.update_cross_axes()

    # シミュレーション実行
    timeline = simulator.simulate(
        initial_points=[ball],
        duration=duration,
        record_interval=0.033  # 30 FPS
    )

    print("=" * 60)
    print()

    return timeline


def create_projectile_simulation(
    duration: float = 2.0,
    initial_velocity_x: float = 1.0,
    initial_velocity_y: float = 1.0,
    gravity: float = 9.8
) -> List[Dict[str, Any]]:
    """
    放物運動のシミュレーションを作成

    Args:
        duration: シミュレーション時間（秒）
        initial_velocity_x: 初期X速度
        initial_velocity_y: 初期Y速度
        gravity: 重力加速度

    Returns:
        時系列Cross構造
    """
    print("\n" + "=" * 60)
    print("🎾 放物運動シミュレーション")
    print("=" * 60)

    simulator = CrossPhysicsSimulator(dt=0.016)

    simulator.add_law(GravityLaw(gravity=gravity))
    simulator.add_law(InertiaLaw())
    simulator.add_law(CollisionLaw(ground_y=-1.0, restitution=0.6))
    simulator.add_law(BoundaryLaw(min_x=-1.0, max_x=1.0))

    # 初期状態: 斜め上に投げる
    ball = PhysicsPoint(
        x=-0.8,
        y=0.0,
        z=0.0,
        velocity_x=initial_velocity_x,
        velocity_y=initial_velocity_y,
        velocity_z=0.0
    )
    ball.update_cross_axes()

    timeline = simulator.simulate(
        initial_points=[ball],
        duration=duration,
        record_interval=0.033
    )

    print("=" * 60)
    print()

    return timeline


def create_horizontal_motion_simulation(
    duration: float = 2.0,
    velocity: float = 1.0
) -> List[Dict[str, Any]]:
    """
    水平等速運動のシミュレーションを作成

    Args:
        duration: シミュレーション時間（秒）
        velocity: 速度

    Returns:
        時系列Cross構造
    """
    print("\n" + "=" * 60)
    print("➡️  水平運動シミュレーション")
    print("=" * 60)

    simulator = CrossPhysicsSimulator(dt=0.016)

    simulator.add_law(InertiaLaw())
    simulator.add_law(BoundaryLaw(min_x=-1.0, max_x=1.0))

    # 初期状態: 左から右へ移動
    ball = PhysicsPoint(
        x=-1.0,
        y=0.0,
        z=0.0,
        velocity_x=velocity,
        velocity_y=0.0,
        velocity_z=0.0
    )
    ball.update_cross_axes()

    timeline = simulator.simulate(
        initial_points=[ball],
        duration=duration,
        record_interval=0.033
    )

    print("=" * 60)
    print()

    return timeline
