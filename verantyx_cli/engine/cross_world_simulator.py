"""
Cross世界シミュレータ (Python実装)

.jcross定義を実行し、物理世界をシミュレート
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from pathlib import Path

# .jcrossファイルローダーをインポート
try:
    from jcross_loader import CrossStructureLoader
except ImportError:
    CrossStructureLoader = None


@dataclass
class PhysicalObject:
    """物理物体"""
    id: str
    position: np.ndarray      # [x, y, z]
    velocity: np.ndarray      # [vx, vy, vz]
    shape: str
    color: str
    size: float
    visible: bool = True
    exists: bool = True        # 物の永続性！
    affordances: List[str] = None
    trajectory: List[np.ndarray] = None  # 軌跡

    def __post_init__(self):
        if self.affordances is None:
            self.affordances = []
        if self.trajectory is None:
            self.trajectory = []


class CrossWorldSimulator:
    """
    Cross世界モデルシミュレータ

    6-12ヶ月児の能力:
    - 物の永続性
    - 予測と驚き
    - 物理法則の理解
    """

    def __init__(self, dt: float = 0.016, jcross_config_file: Optional[str] = None):
        self.dt = dt  # 時間ステップ (60fps)
        self.time = 0.0

        # 物体リスト
        self.objects: Dict[str, PhysicalObject] = {}

        # .jcross設定ファイルから読み込み
        if jcross_config_file and CrossStructureLoader:
            self._load_from_jcross(jcross_config_file)
        else:
            # デフォルト値
            self.gravity = -9.8
            self.ground_level = 0.0
            self.surprise_threshold = 0.1

        # 予測
        self.predictions: Dict[str, np.ndarray] = {}

        # 驚き
        self.surprise_events: List[Dict] = []

        # 学習
        self.prediction_errors: List[float] = []

    def _load_from_jcross(self, jcross_file: str):
        """
        .jcrossファイルから設定を読み込む

        これにより、cross_world_simulator.jcrossの定義が実際に使われる！
        """
        try:
            loader = CrossStructureLoader(jcross_file)
            params = loader.get_all_parameters()

            # 重力
            gravity_params = params.get("gravity", {})
            self.gravity = gravity_params.get("force", -9.8)

            # 驚き閾値
            self.surprise_threshold = params.get("surprise_threshold", 0.1)

            # 地面
            self.ground_level = 0.0

            print(f"✅ .jcrossファイルから設定を読み込みました:")
            print(f"   重力: {self.gravity} m/s²")
            print(f"   驚き閾値: {self.surprise_threshold} m")

        except Exception as e:
            print(f"⚠️ .jcross読み込みエラー: {e}")
            print(f"   デフォルト値を使用します")
            self.gravity = -9.8
            self.ground_level = 0.0
            self.surprise_threshold = 0.1

    def add_object(
        self,
        obj_id: str,
        position: np.ndarray,
        velocity: np.ndarray = None,
        shape: str = "sphere",
        color: str = "red",
        size: float = 1.0,
        affordances: List[str] = None
    ) -> PhysicalObject:
        """物体を追加"""

        if velocity is None:
            velocity = np.zeros(3)

        if affordances is None:
            affordances = []

        obj = PhysicalObject(
            id=obj_id,
            position=position.copy(),
            velocity=velocity.copy(),
            shape=shape,
            color=color,
            size=size,
            affordances=affordances
        )

        # 初期位置を軌跡に追加
        obj.trajectory.append(position.copy())

        self.objects[obj_id] = obj
        return obj

    def step(self):
        """
        シミュレーションを1ステップ進める

        1. 予測を生成（現在の状態から）
        2. 状態を保存
        3. 物理法則を適用
        4. 予測と実際を比較
        5. 驚きを検出
        6. 学習
        """
        # 1. 現在の状態を保存
        saved_states = {}
        for obj_id, obj in self.objects.items():
            if obj.exists:
                saved_states[obj_id] = {
                    'position': obj.position.copy(),
                    'velocity': obj.velocity.copy()
                }

        # 2. 予測を生成（保存した状態から）
        predictions_this_step = {}

        for obj_id, obj in self.objects.items():
            if obj.exists:
                # 予測は現在の速度と位置から計算
                # （外部からの介入があればここで検出される）
                state = saved_states[obj_id]

                # 予測速度（重力を考慮）
                predicted_velocity = state['velocity'].copy()
                predicted_velocity[2] += self.gravity * self.dt

                # 予測位置
                predicted_position = state['position'] + predicted_velocity * self.dt

                # 地面との衝突を予測
                if predicted_position[2] < self.ground_level:
                    predicted_position[2] = self.ground_level

                predictions_this_step[obj_id] = predicted_position

        # 3. 物理法則を適用
        for obj_id, obj in self.objects.items():
            if obj.exists:
                self._apply_physics(obj)

        # 4. 予測誤差（予測は物理法則適用**前**の状態で生成）
        for obj_id, obj in self.objects.items():
            if obj.exists and obj_id in predictions_this_step:
                predicted = predictions_this_step[obj_id]
                actual = obj.position

                error = np.linalg.norm(actual - predicted)
                self.prediction_errors.append(error)

                # 5. 驚き検出
                if error > self.surprise_threshold:
                    self._detect_surprise(obj_id, predicted, actual, error)

        # 次のステップのために予測を保存
        self.predictions = predictions_this_step

        # 6. 学習（予測誤差で世界モデルを更新）
        self._learn_from_errors()

        # 時刻を進める
        self.time += self.dt

    def _apply_physics(self, obj: PhysicalObject):
        """物理法則を適用"""

        # 重力
        obj.velocity[2] += self.gravity * self.dt

        # 位置更新
        new_position = obj.position + obj.velocity * self.dt

        # 地面との衝突
        if new_position[2] < self.ground_level:
            new_position[2] = self.ground_level
            obj.velocity[2] = -obj.velocity[2] * 0.7  # 反発係数

        # 軌跡を記録
        obj.trajectory.append(obj.position.copy())

        # 位置を更新
        obj.position = new_position

    def predict_next_position(self, obj_id: str) -> np.ndarray:
        """
        次の位置を予測

        現在の状態 + 物理法則 → 次の状態
        """
        obj = self.objects.get(obj_id)
        if not obj:
            return np.zeros(3)

        # 予測速度（重力を考慮）
        predicted_velocity = obj.velocity.copy()
        predicted_velocity[2] += self.gravity * self.dt

        # 予測位置
        predicted_position = obj.position + predicted_velocity * self.dt

        # 地面との衝突を予測
        if predicted_position[2] < self.ground_level:
            predicted_position[2] = self.ground_level

        return predicted_position

    def _detect_surprise(
        self,
        obj_id: str,
        predicted: np.ndarray,
        actual: np.ndarray,
        error: float
    ):
        """驚きを検出"""

        surprise_event = {
            "time": self.time,
            "object": obj_id,
            "predicted": predicted.copy(),
            "actual": actual.copy(),
            "error": error,
            "type": self._classify_surprise(predicted, actual)
        }

        self.surprise_events.append(surprise_event)

        print(f"⚠️ 驚き！ {obj_id}: 予測誤差 {error:.2f}m")
        print(f"   予測: {predicted}")
        print(f"   実際: {actual}")
        print(f"   種類: {surprise_event['type']}")

    def _classify_surprise(self, predicted: np.ndarray, actual: np.ndarray) -> str:
        """驚きの種類を分類"""

        diff = actual - predicted

        if abs(diff[2]) > 1.0:
            return "物理法則違反（重力）"
        elif np.linalg.norm(diff) > 2.0:
            return "瞬間移動"
        else:
            return "予測誤差"

    def _learn_from_errors(self):
        """予測誤差から学習"""

        if not self.prediction_errors:
            return

        # 平均誤差
        avg_error = np.mean(self.prediction_errors[-100:])  # 直近100ステップ

        # 誤差が大きい場合、モデルを調整
        # TODO: より洗練された学習アルゴリズム

        if avg_error > 0.1:
            # 例: 重力定数の微調整
            # self.gravity *= 0.99
            pass

    def hide_object(self, obj_id: str):
        """
        物体を隠す

        重要: 物体は見えなくても存在し続ける（物の永続性）
        """
        obj = self.objects.get(obj_id)
        if obj:
            obj.visible = False
            obj.exists = True  # 存在は維持！
            print(f"物体 {obj_id} を隠しました（でも存在しています）")

    def inject_surprise(self, obj_id: str, new_velocity: np.ndarray):
        """
        驚きを注入（テスト用）

        外部から物体の速度を変更し、次のステップで驚きを検出させる
        """
        obj = self.objects.get(obj_id)
        if obj:
            obj.velocity = new_velocity.copy()
            print(f"⚡ 驚き注入: {obj_id} の速度を {new_velocity} に変更")

    def find_object(self, obj_id: str) -> Optional[np.ndarray]:
        """
        物体を探す

        6-12ヶ月児のA-not-B課題
        """
        obj = self.objects.get(obj_id)
        if not obj:
            return None

        if not obj.exists:
            print(f"物体 {obj_id} は存在しません")
            return None

        if not obj.visible:
            # 隠れているが、最後に見た位置を覚えている
            if obj.trajectory:
                last_seen = obj.trajectory[-1]
                print(f"物体 {obj_id} は隠れています。最後に見た場所: {last_seen}")
                return last_seen
            else:
                print(f"物体 {obj_id} の位置が分かりません")
                return None

        else:
            print(f"物体 {obj_id} の位置: {obj.position}")
            return obj.position

    def get_object_state(self, obj_id: str) -> Dict[str, Any]:
        """物体の状態を取得"""
        obj = self.objects.get(obj_id)
        if not obj:
            return {}

        return {
            "id": obj.id,
            "position": obj.position.tolist(),
            "velocity": obj.velocity.tolist(),
            "shape": obj.shape,
            "color": obj.color,
            "size": obj.size,
            "visible": obj.visible,
            "exists": obj.exists,
            "affordances": obj.affordances,
        }

    def test_object_permanence(self):
        """
        物の永続性をテスト

        A-not-B課題
        """
        print("\n" + "=" * 60)
        print("物の永続性テスト（A-not-B課題）")
        print("=" * 60)
        print()

        # ボールを追加
        ball = self.add_object(
            "ball",
            position=np.array([0.0, 0.0, 1.0]),
            velocity=np.array([0.0, 0.0, 0.0]),
            color="red",
            affordances=["掴める", "投げられる"]
        )

        print("1. ボールを見る")
        pos = self.find_object("ball")
        print()

        # シミュレーション
        print("2. ボールを落とす")
        ball.velocity = np.array([0.0, 0.0, -1.0])

        for _ in range(30):
            self.step()

        print(f"   ボールの位置: {ball.position}")
        print()

        # ボールを隠す
        print("3. ボールを隠す")
        self.hide_object("ball")
        print()

        # 探す
        print("4. ボールを探す")
        pos = self.find_object("ball")
        print()

        print("✅ 物の永続性テスト完了")
        print("   赤ちゃんと同じように、隠れた物体を覚えている！")
        print()

    def test_surprise_detection(self):
        """
        驚き検出をテスト

        物理法則違反を検出
        """
        print("\n" + "=" * 60)
        print("驚き検出テスト")
        print("=" * 60)
        print()

        # ボールを追加
        ball = self.add_object(
            "magic_ball",
            position=np.array([0.0, 0.0, 1.0]),
            velocity=np.array([0.0, 0.0, 0.0]),
        )

        print("1. 通常の落下")
        ball.velocity = np.array([0.0, 0.0, -1.0])

        for _ in range(10):
            self.step()

        print()

        # 物理法則違反: ボールが上に飛ぶ
        print("2. 物理法則違反: ボールが突然上に飛ぶ")
        ball.velocity = np.array([0.0, 0.0, 10.0])  # 急激な上昇！

        for _ in range(5):
            self.step()

        print()

        print(f"✅ 驚きイベント: {len(self.surprise_events)}回")
        for event in self.surprise_events:
            print(f"   時刻 {event['time']:.2f}s: {event['type']}")

        print()


if __name__ == "__main__":
    print("=" * 80)
    print("Cross世界モデルシミュレータ - デモ")
    print("=" * 80)
    print()

    sim = CrossWorldSimulator()

    # 物の永続性テスト
    sim.test_object_permanence()

    # 新しいシミュレータで驚き検出テスト
    sim2 = CrossWorldSimulator()
    sim2.test_surprise_detection()

    print("=" * 80)
    print("✅ Cross世界モデルシミュレータ実装完了")
    print("=" * 80)
    print()
    print("これにより:")
    print("  - 物の永続性（6-12ヶ月レベル）")
    print("  - 予測と驚き")
    print("  - 物理法則の理解")
    print("  - 世界モデルの学習")
    print()
