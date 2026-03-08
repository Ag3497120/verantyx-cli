# Cross World Truth System Design
Cross構造における世界の真理システム設計

## 問題の本質

現在の形状認識が「No shapes detected」となる根本原因：

```
現状: 静的なパターンマッチングのみ
画像 → 点配置 → パターン照合 → 形状認識

問題:
- 世界の法則が組み込まれていない
- 物理的な振る舞いの知識がない
- 時間経過による変化の理解がない
- 因果関係の認識ができない
```

**必要なこと**: Cross構造に「世界の真理」を組み込む

## 世界の真理とは

人間が無意識に理解している物理法則・因果関係：

### 1. 重力法則
```
真理: 物体は下に落ちる
Cross表現:
- DOWN軸の値が時間とともに増加
- UP軸の値が時間とともに減少
- 加速度: DOWN軸の増加率が一定
```

### 2. 慣性法則
```
真理: 動いている物体は動き続ける
Cross表現:
- RIGHT/LEFT軸の変化が等速で継続
- 外力がない限り軸の変化率が一定
```

### 3. 衝突法則
```
真理: 物体同士がぶつかると跳ね返る
Cross表現:
- 2つの点が接近（距離 < threshold）
- RIGHT/LEFT軸の変化方向が反転
- DOWN/UP軸の変化率が変化
```

### 4. 遮蔽法則
```
真理: 手前の物体が奥の物体を隠す
Cross表現:
- FRONT軸の値が大きい点が優先
- BACK軸の値が小さい点は見えない
```

### 5. 因果法則
```
真理: 原因があって結果がある
Cross表現:
- TIME軸での前後関係
- 状態変化の連鎖
```

## アーキテクチャ: Cross物理シミュレータ

```
【物理シミュレータ】
  ↓
【1】初期状態を定義（Cross構造）
  例: 空中の球体（1点）
  position: (x=0, y=1, z=0)
  velocity: (vx=0, vy=0, vz=0)
  ↓
【2】物理法則を適用（重力）
  法則: vy -= gravity * dt
  法則: y += vy * dt
  ↓
【3】Cross構造を更新
  UP軸: 1.0 → 0.9 → 0.8 → ... → 0.0
  DOWN軸: 0.0 → 0.1 → 0.2 → ... → 1.0
  TIME軸: t0 → t1 → t2 → ... → tn
  ↓
【4】時系列Cross構造を記憶
  「落下パターン」として断片記憶に保存
  ↓
【5】実際の動画と照合
  動画のCross構造変化 vs 落下パターン
  → マッチすれば「落下している」と認識
```

## 実装: Cross物理エンジン

### 1. 物理法則の定義

```python
class CrossPhysicsLaw:
    """Cross構造における物理法則"""

    def __init__(self, name: str):
        self.name = name

    def apply(self, point: CrossPoint, dt: float) -> CrossPoint:
        """物理法則を点に適用"""
        raise NotImplementedError


class GravityLaw(CrossPhysicsLaw):
    """重力法則"""

    def __init__(self, gravity: float = 9.8):
        super().__init__("Gravity")
        self.gravity = gravity

    def apply(self, point: CrossPoint, dt: float) -> CrossPoint:
        """
        重力を適用

        DOWN軸方向に加速
        """
        # 速度を更新（DOWN方向に加速）
        point.velocity_down += self.gravity * dt

        # 位置を更新
        point.down += point.velocity_down * dt
        point.up = max(0, 1.0 - point.down)

        # Y座標も更新
        point.y -= point.velocity_down * dt

        return point


class InertiaLaw(CrossPhysicsLaw):
    """慣性法則"""

    def __init__(self):
        super().__init__("Inertia")

    def apply(self, point: CrossPoint, dt: float) -> CrossPoint:
        """
        慣性を適用

        現在の速度で等速運動
        """
        # X方向
        point.x += point.velocity_right * dt
        point.right = (point.x + 1) / 2  # [-1, 1] → [0, 1]
        point.left = 1.0 - point.right

        # Z方向
        point.z += point.velocity_front * dt
        point.front = (point.z + 1) / 2
        point.back = 1.0 - point.front

        return point


class CollisionLaw(CrossPhysicsLaw):
    """衝突法則"""

    def __init__(self, restitution: float = 0.8):
        super().__init__("Collision")
        self.restitution = restitution  # 反発係数

    def apply(self, point: CrossPoint, dt: float) -> CrossPoint:
        """
        地面との衝突を処理
        """
        # 地面（y=0）に到達したか？
        if point.y <= 0 and point.velocity_down > 0:
            # 跳ね返り
            point.velocity_down = -point.velocity_down * self.restitution
            point.y = 0
            point.down = 1.0
            point.up = 0.0

        return point
```

### 2. Cross物理シミュレータ

```python
class CrossPhysicsSimulator:
    """Cross構造物理シミュレータ"""

    def __init__(self):
        self.laws = []
        self.time = 0.0
        self.dt = 0.016  # 60 FPS

    def add_law(self, law: CrossPhysicsLaw):
        """物理法則を追加"""
        self.laws.append(law)

    def simulate(
        self,
        initial_points: List[CrossPoint],
        duration: float
    ) -> List[Dict[str, Any]]:
        """
        物理シミュレーションを実行

        Args:
            initial_points: 初期点群
            duration: シミュレーション時間（秒）

        Returns:
            時系列Cross構造のリスト
        """
        # 点をコピー
        points = [copy.deepcopy(p) for p in initial_points]

        # 時系列記録
        timeline = []

        num_steps = int(duration / self.dt)

        for step in range(num_steps):
            # 各物理法則を適用
            for point in points:
                for law in self.laws:
                    point = law.apply(point, self.dt)

            # 現在の状態を記録
            snapshot = {
                "time": self.time,
                "points": [copy.deepcopy(p) for p in points],
                "cross_structure": self._to_cross_structure(points)
            }

            timeline.append(snapshot)

            self.time += self.dt

        return timeline
```

### 3. 世界真理記憶バンク

```python
class WorldTruthMemoryBank:
    """世界の真理を記憶するバンク"""

    def __init__(self):
        self.truths = {}

    def learn_truth(
        self,
        truth_name: str,
        simulation_timeline: List[Dict[str, Any]]
    ):
        """
        シミュレーションから真理を学習

        Args:
            truth_name: 真理の名前（例: "falling"）
            simulation_timeline: シミュレーション時系列
        """
        print(f"\n📚 世界の真理を学習中: {truth_name}")

        # 時系列パターンを抽出
        pattern = self._extract_temporal_pattern(simulation_timeline)

        # 6軸の変化特性を抽出
        axis_changes = self._extract_axis_changes(simulation_timeline)

        # 真理として記憶
        self.truths[truth_name] = {
            "name": truth_name,
            "temporal_pattern": pattern,
            "axis_changes": axis_changes,
            "duration": simulation_timeline[-1]["time"],
            "num_frames": len(simulation_timeline)
        }

        print(f"  ✅ 真理 '{truth_name}' を記憶しました")

    def _extract_temporal_pattern(
        self,
        timeline: List[Dict[str, Any]]
    ) -> Dict[str, List[float]]:
        """時系列パターンを抽出"""
        pattern = {
            "UP": [],
            "DOWN": [],
            "RIGHT": [],
            "LEFT": [],
            "FRONT": [],
            "BACK": []
        }

        for snapshot in timeline:
            points = snapshot["points"]

            if not points:
                continue

            # 各軸の平均値を記録
            for axis_name in pattern.keys():
                axis_value = np.mean([
                    getattr(p, axis_name.lower())
                    for p in points
                ])
                pattern[axis_name].append(axis_value)

        return pattern

    def _extract_axis_changes(
        self,
        timeline: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """軸の変化特性を抽出"""
        changes = {}

        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
            values = []

            for snapshot in timeline:
                points = snapshot["points"]
                if points:
                    avg_value = np.mean([
                        getattr(p, axis_name.lower())
                        for p in points
                    ])
                    values.append(avg_value)

            if not values:
                continue

            # 変化特性を計算
            changes[axis_name] = {
                "trend": self._detect_trend(values),  # "increasing", "decreasing", "constant"
                "rate": self._calculate_change_rate(values),
                "pattern_type": self._classify_pattern(values)  # "linear", "accelerating", "decelerating"
            }

        return changes

    def recognize_truth(
        self,
        video_timeline: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        動画のCross構造時系列から真理を認識

        Args:
            video_timeline: 動画のCross構造時系列

        Returns:
            各真理との類似度スコア
        """
        scores = {}

        for truth_name, truth_data in self.truths.items():
            # 時系列パターンのマッチング
            score = self._match_temporal_pattern(
                video_timeline,
                truth_data["temporal_pattern"]
            )

            scores[truth_name] = score

        return scores
```

## 学習フロー

### Step 1: 基本的な物理真理を学習

```python
# 1. 落下シミュレーション
simulator = CrossPhysicsSimulator()
simulator.add_law(GravityLaw(gravity=9.8))
simulator.add_law(CollisionLaw(restitution=0.8))

# 初期状態: 空中の球
ball = CrossPoint(x=0, y=1, z=0)
ball.velocity_down = 0

# シミュレーション実行
timeline = simulator.simulate(
    initial_points=[ball],
    duration=2.0  # 2秒
)

# 真理記憶バンクに学習
truth_bank = WorldTruthMemoryBank()
truth_bank.learn_truth("falling", timeline)


# 2. 水平移動シミュレーション
simulator = CrossPhysicsSimulator()
simulator.add_law(InertiaLaw())

ball = CrossPoint(x=-1, y=0.5, z=0)
ball.velocity_right = 1.0  # 右方向に移動

timeline = simulator.simulate([ball], duration=2.0)
truth_bank.learn_truth("horizontal_motion", timeline)


# 3. 放物運動シミュレーション
simulator = CrossPhysicsSimulator()
simulator.add_law(GravityLaw())
simulator.add_law(InertiaLaw())

ball = CrossPoint(x=-1, y=1, z=0)
ball.velocity_right = 1.0
ball.velocity_down = 0

timeline = simulator.simulate([ball], duration=2.0)
truth_bank.learn_truth("projectile", timeline)
```

### Step 2: 動画との照合

```python
# 動画をCross構造時系列に変換
video_timeline = convert_video_to_cross_timeline(video_path)

# 真理を認識
scores = truth_bank.recognize_truth(video_timeline)

# 結果:
# {
#   "falling": 0.89,
#   "horizontal_motion": 0.12,
#   "projectile": 0.45
# }
# → この動画では「落下」が起きている！
```

## JCross実装

### 1. 物理シミュレーション用プロセッサ

25個の新プロセッサ:
1. `physics.create_point` - 物理点を作成
2. `physics.set_velocity` - 速度を設定
3. `physics.add_gravity` - 重力法則を追加
4. `physics.add_inertia` - 慣性法則を追加
5. `physics.add_collision` - 衝突法則を追加
6. `physics.simulate` - シミュレーション実行
7. `truth.extract_pattern` - パターン抽出
8. `truth.learn` - 真理学習
9. `truth.recognize` - 真理認識
10. `truth.save` - 真理保存
... 等

### 2. JCrossプログラム例

```jcross
# 落下真理学習プログラム

# 物理点を作成
実行する physics.create_point = {
  "x": 0,
  "y": 1,
  "z": 0,
  "velocity_down": 0
}
入れる ball

# 重力法則を追加
実行する physics.add_gravity = {"gravity": 9.8}

# 衝突法則を追加
実行する physics.add_collision = {"restitution": 0.8}

# 2秒間シミュレーション
読む ball
実行する physics.simulate = {
  "duration": 2.0,
  "dt": 0.016
}
入れる falling_timeline

# パターン抽出
読む falling_timeline
実行する truth.extract_pattern
入れる falling_pattern

# 真理として学習
読む falling_pattern
実行する truth.learn = {"name": "falling"}

# 真理を保存
実行する truth.save
```

## 統合: 形状認識 + 物理真理

```
動画
  ↓
【1】各フレームを多層Cross構造に変換
  ↓
【2】時系列Cross構造を生成
  ↓
【3】物理真理バンクと照合
  - 落下している？
  - 移動している？
  - 回転している？
  ↓
【4】物理的文脈を考慮した形状認識
  - 落下中 → 「物体」である可能性が高い
  - 静止 → 「背景」や「地面」の可能性
  ↓
【5】より正確な認識結果
```

## 次のステップ

1. `cross_physics_simulator.py` - 物理シミュレータ実装
2. `world_truth_memory.py` - 世界真理記憶バンク
3. `physics_processors.py` - 物理シミュレーション用プロセッサ（25個）
4. `learn_world_truths.jcross` - 世界真理学習プログラム
5. `run_truth_learning.py` - 真理学習ランナー
6. 形状認識との統合
