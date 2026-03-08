# Camera-Based Object Learning Design
カメラベースのオブジェクト学習設計

## コンセプト

MacBookのカメラでリアルタイムに物を見せながら、Cross構造で学習させる。

```
ユーザー: カメラにりんごを見せる
システム: 「これは何ですか？」
ユーザー: 「りんご」と入力
システム: りんごのCross構造を記憶

ユーザー: カメラにペンを見せる
システム: 「これは何ですか？」
ユーザー: 「ペン」と入力
システム: ペンのCross構造を記憶

ユーザー: カメラに人の顔を見せる
システム: 「これは何ですか？」
ユーザー: 「人」と入力
システム: 人のCross構造を記憶

---

後で同じ物を見せると...
システム: 「これは りんご です（信頼度: 89%）」
```

## 学習フロー

```
【1】カメラ起動
  ↓
【2】リアルタイムプレビュー表示
  ↓
【3】ユーザーが物をカメラに見せる
  ↓
【4】スペースキーでキャプチャ
  ↓
【5】Cross構造に変換（多層、26万点）
  ↓
【6】「これは何ですか？」と質問
  ↓
【7】ユーザーがラベル入力（例: "りんご"）
  ↓
【8】オブジェクトCross構造データベースに保存
  object_name: "りんご"
  cross_structure: {...}
  ↓
【9】「りんご を記憶しました」
  ↓
【10】次の物を学習 or 終了
```

## 認識フロー

```
【1】カメラで物を見る
  ↓
【2】リアルタイムCross変換
  ↓
【3】データベースと照合
  ↓
【4】最も類似したオブジェクトを検出
  ↓
【5】「これは りんご です（89%）」と表示
```

## UI設計

```
┌────────────────────────────────────────────────────────┐
│ Verantyx Vision - Camera Learning                     │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌────────────────────────────────────────────┐       │
│  │                                            │       │
│  │         [カメラプレビュー]                 │       │
│  │                                            │       │
│  │            640 x 480                       │       │
│  │                                            │       │
│  └────────────────────────────────────────────┘       │
│                                                        │
│  状態: カメラ起動中                                     │
│  学習済みオブジェクト数: 5                              │
│                                                        │
│  [スペース] キャプチャ  [r] 認識モード  [q] 終了        │
│                                                        │
├────────────────────────────────────────────────────────┤
│ 学習済みオブジェクト:                                   │
│  - りんご (3サンプル)                                   │
│  - ペン (2サンプル)                                     │
│  - 人 (5サンプル)                                       │
│  - マグカップ (1サンプル)                               │
│  - 本 (2サンプル)                                       │
└────────────────────────────────────────────────────────┘
```

## キャプチャモード

```
[スペースキー押下]

┌────────────────────────────────────────────────────────┐
│ キャプチャしました！                                     │
├────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐       │
│  │         [キャプチャ画像]                    │       │
│  └────────────────────────────────────────────┘       │
│                                                        │
│  Cross構造に変換中...                                   │
│  └─ Layer 0: 200,000点                                 │
│  └─ Layer 1:  50,000点                                 │
│  └─ Layer 2:  10,000点                                 │
│  └─ Layer 3:   1,000点                                 │
│  └─ Layer 4:     100点                                 │
│                                                        │
│  これは何ですか？                                       │
│  > りんご_                                              │
│                                                        │
│  [Enter] 保存  [Esc] キャンセル                         │
└────────────────────────────────────────────────────────┘
```

## 認識モード

```
[r キー押下]

┌────────────────────────────────────────────────────────┐
│ 認識モード                                              │
├────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐       │
│  │         [カメラプレビュー]                 │       │
│  └────────────────────────────────────────────┘       │
│                                                        │
│  リアルタイム認識中...                                  │
│                                                        │
│  🍎 これは りんご です                                  │
│     信頼度: 89%                                         │
│                                                        │
│  類似オブジェクト:                                      │
│    1. りんご (89%)                                      │
│    2. みかん (23%)                                      │
│    3. マグカップ (12%)                                  │
│                                                        │
│  [スペース] 学習モードに戻る  [q] 終了                  │
└────────────────────────────────────────────────────────┘
```

## 実装

### 1. カメラキャプチャ

```python
import cv2

class CameraCapture:
    """MacBookカメラキャプチャ"""

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None

    def start(self):
        """カメラを起動"""
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            raise RuntimeError("カメラを開けませんでした")

        # 解像度設定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def read_frame(self):
        """フレームを読み取り"""
        ret, frame = self.cap.read()

        if not ret:
            return None

        return frame

    def release(self):
        """カメラを解放"""
        if self.cap:
            self.cap.release()
```

### 2. インタラクティブ学習UI

```python
class InteractiveLearningUI:
    """インタラクティブ学習UI"""

    def __init__(self):
        self.camera = CameraCapture()
        self.object_db = ObjectCrossDatabase()
        self.mode = "learning"  # "learning" or "recognition"

    def run(self):
        """UIを実行"""
        print("Verantyx Vision - Camera Learning")
        print("=" * 60)
        print()
        print("操作:")
        print("  [スペース] キャプチャ＆学習")
        print("  [r] 認識モード切り替え")
        print("  [q] 終了")
        print()

        self.camera.start()

        try:
            while True:
                # フレームを取得
                frame = self.camera.read_frame()

                if frame is None:
                    break

                # モードに応じて処理
                if self.mode == "learning":
                    self._learning_mode(frame)
                else:
                    self._recognition_mode(frame)

                # プレビュー表示
                cv2.imshow("Verantyx Vision", frame)

                # キー入力
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    break
                elif key == ord(' '):
                    self._capture_and_learn(frame)
                elif key == ord('r'):
                    self._toggle_mode()

        finally:
            self.camera.release()
            cv2.destroyAllWindows()

    def _capture_and_learn(self, frame):
        """キャプチャして学習"""
        print("\n📸 キャプチャしました！")
        print()

        # Cross構造に変換
        print("Cross構造に変換中...")
        cross_structure = self._frame_to_cross(frame)
        print("  ✅ 変換完了")
        print()

        # ラベル入力
        object_name = input("これは何ですか？ > ")

        if not object_name:
            print("キャンセルしました")
            return

        # データベースに保存
        self.object_db.add_object(object_name, cross_structure)

        print(f"✅ '{object_name}' を記憶しました")
        print()

    def _recognition_mode(self, frame):
        """認識モードで処理"""
        # リアルタイムCross変換（低解像度で高速）
        cross_structure = self._frame_to_cross(frame, quality="low")

        # オブジェクト認識
        results = self.object_db.recognize(cross_structure, top_k=3)

        # 画面にオーバーレイ表示
        if results:
            best_match = results[0]
            text = f"{best_match['object']}: {best_match['confidence']:.1f}%"

            cv2.putText(
                frame, text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1,
                (0, 255, 0), 2
            )
```

### 3. オブジェクトCross構造データベース

```python
class ObjectCrossDatabase:
    """オブジェクトCross構造データベース"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".verantyx" / "object_database.json"

        self.db_path = db_path
        self.objects = {}  # object_name -> [cross_structures]

        if self.db_path.exists():
            self.load()

    def add_object(
        self,
        object_name: str,
        cross_structure: Dict[str, Any]
    ):
        """オブジェクトを追加"""
        if object_name not in self.objects:
            self.objects[object_name] = []

        self.objects[object_name].append({
            "cross_structure": cross_structure,
            "timestamp": datetime.now().isoformat()
        })

        self.save()

    def recognize(
        self,
        cross_structure: Dict[str, Any],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """オブジェクトを認識"""
        if not self.objects:
            return []

        scores = {}

        for object_name, samples in self.objects.items():
            # 各サンプルとの類似度を計算
            sample_scores = []

            for sample in samples:
                similarity = self._calculate_similarity(
                    cross_structure,
                    sample["cross_structure"]
                )
                sample_scores.append(similarity)

            # 最高スコアを採用
            scores[object_name] = max(sample_scores)

        # スコアでソート
        sorted_objects = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 上位k個を返す
        results = []

        for object_name, score in sorted_objects[:top_k]:
            results.append({
                "object": object_name,
                "score": score,
                "confidence": score * 100
            })

        return results

    def _calculate_similarity(
        self,
        cross1: Dict[str, Any],
        cross2: Dict[str, Any]
    ) -> float:
        """Cross構造の類似度を計算"""
        # 各軸の平均値を比較
        axes1 = cross1.get("axes", {})
        axes2 = cross2.get("axes", {})

        similarities = []

        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
            mean1 = axes1.get(axis_name, {}).get("mean", 0.5)
            mean2 = axes2.get(axis_name, {}).get("mean", 0.5)

            diff = abs(mean1 - mean2)
            similarity = 1.0 - diff

            similarities.append(similarity)

        return float(np.mean(similarities))

    def save(self):
        """データベースを保存"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "objects": self.objects
        }

        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self):
        """データベースを読み込み"""
        with open(self.db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.objects = data.get("objects", {})

    def list_objects(self) -> List[Dict[str, Any]]:
        """学習済みオブジェクト一覧"""
        objects = []

        for name, samples in self.objects.items():
            objects.append({
                "name": name,
                "sample_count": len(samples)
            })

        return objects
```

## 使い方

```bash
# カメラ学習を起動
python -m verantyx_cli.vision.learn_from_camera

# 操作:
# 1. 物をカメラに見せる
# 2. スペースキーでキャプチャ
# 3. 「これは何ですか？」に答える（例: りんご）
# 4. Enterで保存
# 5. 繰り返し

# 認識モード:
# r キーで認識モードに切り替え
# → リアルタイムで物を認識
```

## 学習データの蓄積

```
~/.verantyx/object_database.json

{
  "りんご": [
    {"cross_structure": {...}, "timestamp": "2024-..."},
    {"cross_structure": {...}, "timestamp": "2024-..."},
    {"cross_structure": {...}, "timestamp": "2024-..."}
  ],
  "ペン": [
    {"cross_structure": {...}, "timestamp": "2024-..."},
    {"cross_structure": {...}, "timestamp": "2024-..."}
  ],
  "人": [
    {"cross_structure": {...}, "timestamp": "2024-..."},
    ...
  ]
}
```

## 世界の真理との統合

学習したオブジェクトに物理的振る舞いを関連付け:

```python
# りんごは落下する
object_db.set_behavior("りんご", truth="falling")

# ペンは落下する
object_db.set_behavior("ペン", truth="falling")

# 人は動く
object_db.set_behavior("人", truth="horizontal_motion")
```

これにより:
- オブジェクトを認識
- そのオブジェクトの物理的振る舞いを予測
- より深い理解

## 次のステップ

1. `camera_capture.py` - カメラキャプチャ
2. `interactive_learning_ui.py` - インタラクティブUI
3. `object_cross_database.py` - オブジェクトデータベース
4. `learn_from_camera.py` - メインプログラム
