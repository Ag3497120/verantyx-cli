# Adaptive Resolution & Self-Modifying JCross Design
状態遷移時の適応的解像度とJCross自己変容設計

## 問題の本質

```
動画での状態遷移:
フレーム 0: UIが静止
フレーム 50: ボタンがクリックされる ← 状態遷移！
フレーム 51: 画面が切り替わる
フレーム 52: 新しいUIが表示される

現在の問題:
- 固定解像度（200,000点）では変化を捉えきれない
- .jcrossコードが固定で、状態に応じて変化しない
```

## 解決策

### 1. 適応的解像度システム

```
通常時: 低解像度（50,000点）
  ↓
状態遷移検出！
  ↓
解像度を自動増加（200,000点 → 500,000点 → 1,000,000点）
  ↓
詳細解析
  ↓
遷移完了検出
  ↓
解像度を戻す（50,000点）
```

### 2. JCross自己変容システム

```jcross
# 初期コード（低解像度）
実行する convert.frame = {"max_points": 50000}

# 状態遷移を検出したら...
# ↓ JCrossコード自体を書き換え！

# 変容後のコード（高解像度）
実行する convert.frame = {"max_points": 500000}
実行する analyze.detail = {"enable": true}
実行する track.objects = {"precision": "high"}
```

## アーキテクチャ

### フロー全体

```
動画フレーム
  ↓
【1】低解像度で解析（50,000点）
  ↓
【2】フレーム間差分を計算
  ↓
【3】差分が閾値を超える？
  YES → 状態遷移検出！
    ↓
  【4】解像度を段階的に上げる
    50K → 100K → 200K → 500K → 1M
    ↓
  【5】JCrossコードを動的生成
    現在の状態に応じたコードを生成
    ↓
  【6】高解像度で詳細解析
    ↓
  【7】遷移完了を検出
    ↓
  【8】解像度を戻す & コードをリセット
    ↓
  NO → 通常解析を継続
```

### 状態遷移検出

```python
def detect_state_transition(
    prev_frame_cross: Dict,
    curr_frame_cross: Dict
) -> Dict[str, Any]:
    """
    状態遷移を検出

    Returns:
        {
            "is_transition": bool,
            "transition_magnitude": float,  # 0.0 〜 1.0
            "transition_type": str,  # "sudden", "gradual", "none"
            "affected_regions": List[bbox]
        }
    """
    # 1. 各軸の変化を計算
    axis_changes = {}

    for axis in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
        prev_mean = prev_frame_cross["axes"][axis]["mean"]
        curr_mean = curr_frame_cross["axes"][axis]["mean"]

        change = abs(curr_mean - prev_mean)
        axis_changes[axis] = change

    # 2. 総変化量を計算
    total_change = sum(axis_changes.values())

    # 3. 閾値判定
    if total_change > 0.3:
        transition_type = "sudden"
        magnitude = total_change
    elif total_change > 0.1:
        transition_type = "gradual"
        magnitude = total_change
    else:
        transition_type = "none"
        magnitude = 0.0

    return {
        "is_transition": total_change > 0.1,
        "transition_magnitude": magnitude,
        "transition_type": transition_type,
        "axis_changes": axis_changes
    }
```

### 適応的解像度制御

```python
class AdaptiveResolutionController:
    """適応的解像度コントローラ"""

    # 解像度レベル
    RESOLUTION_LEVELS = {
        "very_low": 10000,
        "low": 50000,
        "medium": 100000,
        "high": 200000,
        "very_high": 500000,
        "ultra": 1000000
    }

    def __init__(self):
        self.current_level = "low"
        self.transition_active = False

    def update(self, transition_info: Dict) -> str:
        """
        遷移情報に基づいて解像度レベルを更新

        Returns:
            新しい解像度レベル
        """
        if not transition_info["is_transition"]:
            # 遷移なし → 通常レベルに戻す
            if self.transition_active:
                self.current_level = self._decrease_level()
                self.transition_active = False
            return self.current_level

        # 遷移あり → 解像度を上げる
        self.transition_active = True
        magnitude = transition_info["transition_magnitude"]

        if magnitude > 0.5:
            # 大きな変化 → 最高解像度
            self.current_level = "ultra"
        elif magnitude > 0.3:
            # 中程度の変化 → 高解像度
            self.current_level = "very_high"
        else:
            # 小さい変化 → 中解像度
            self.current_level = "high"

        return self.current_level

    def get_max_points(self) -> int:
        """現在の解像度レベルの最大点数を取得"""
        return self.RESOLUTION_LEVELS[self.current_level]
```

### JCross自己変容システム

```python
class SelfModifyingJCrossGenerator:
    """JCrossコード自己変容生成器"""

    def generate_code(
        self,
        state: Dict[str, Any]
    ) -> str:
        """
        現在の状態に応じてJCrossコードを動的生成

        Args:
            state: {
                "resolution_level": str,
                "transition_active": bool,
                "transition_type": str,
                "focus_regions": List[bbox]
            }

        Returns:
            JCrossコード（文字列）
        """
        code_lines = []

        # 1. 解像度設定
        max_points = self._get_max_points(state["resolution_level"])

        code_lines.append(f"# 適応的解像度: {state['resolution_level']}")
        code_lines.append(f"# 最大点数: {max_points:,}")
        code_lines.append(f"")
        code_lines.append(f"実行する convert.frame = {{")
        code_lines.append(f"  \"max_points\": {max_points},")
        code_lines.append(f"  \"quality\": \"{state['resolution_level']}\"")
        code_lines.append(f"}}")
        code_lines.append(f"入れる current_frame")
        code_lines.append(f"")

        # 2. 遷移検出が有効な場合
        if state["transition_active"]:
            code_lines.append(f"# 状態遷移検出モード")
            code_lines.append(f"")

            # 詳細解析を有効化
            code_lines.append(f"実行する analyze.detail = {{")
            code_lines.append(f"  \"enable\": true,")
            code_lines.append(f"  \"precision\": \"high\"")
            code_lines.append(f"}}")
            code_lines.append(f"")

            # オブジェクト追跡を有効化
            code_lines.append(f"実行する track.objects = {{")
            code_lines.append(f"  \"enable\": true,")
            code_lines.append(f"  \"method\": \"dense\"")
            code_lines.append(f"}}")
            code_lines.append(f"")

            # 焦点領域がある場合
            if state.get("focus_regions"):
                code_lines.append(f"# 焦点領域の詳細解析")
                for i, bbox in enumerate(state["focus_regions"]):
                    x1, y1, x2, y2 = bbox
                    code_lines.append(f"実行する analyze.region = {{")
                    code_lines.append(f"  \"bbox\": [{x1}, {y1}, {x2}, {y2}],")
                    code_lines.append(f"  \"max_points\": {max_points * 2}")
                    code_lines.append(f"}}")
                    code_lines.append(f"入れる region_{i}")
                    code_lines.append(f"")

        else:
            # 通常モード
            code_lines.append(f"# 通常解析モード")
            code_lines.append(f"")

        # 3. 差分計算
        code_lines.append(f"# フレーム間差分計算")
        code_lines.append(f"読む prev_frame")
        code_lines.append(f"読む current_frame")
        code_lines.append(f"実行する calculate.diff")
        code_lines.append(f"入れる frame_diff")
        code_lines.append(f"")

        # 4. 遷移検出
        code_lines.append(f"# 状態遷移検出")
        code_lines.append(f"読む frame_diff")
        code_lines.append(f"実行する detect.transition")
        code_lines.append(f"入れる transition_info")
        code_lines.append(f"")

        # 5. 解像度更新判定
        code_lines.append(f"# 解像度レベル更新")
        code_lines.append(f"読む transition_info")
        code_lines.append(f"実行する update.resolution")
        code_lines.append(f"入れる new_resolution_level")
        code_lines.append(f"")

        # 6. 自己変容トリガー
        code_lines.append(f"# 必要に応じてコードを再生成")
        code_lines.append(f"読む new_resolution_level")
        code_lines.append(f"読む transition_info")
        code_lines.append(f"実行する regenerate.code_if_needed")
        code_lines.append(f"")

        return "\n".join(code_lines)
```

### JCross実装例

```jcross
# adaptive_video_analysis.jcross
# 適応的動画解析プログラム（自己変容型）

# ============================================================
# 初期化
# ============================================================

# 初期解像度レベル
"low"
入れる resolution_level
捨てる

0
入れる frame_index
捨てる

# 前フレームを初期化（NULL）
実行する create.null_frame
入れる prev_frame
捨てる

# ============================================================
# フレーム処理ループ（自己変容）
# ============================================================

ラベル PROCESS_FRAME

# 【1】現在の状態を取得
読む resolution_level
読む frame_index
実行する get.current_state
入れる current_state
捨てる

# 【2】状態に応じたJCrossコードを生成
読む current_state
実行する generate.jcross_code
入れる generated_code
捨てる

# 【3】生成されたコードを実行（自己変容！）
読む generated_code
実行する eval.jcross
入れる frame_result
捨てる

# 【4】遷移情報を取得
読む frame_result
取り出す transition_info

# 【5】遷移が検出された場合
取り出す is_transition
条件ジャンプ HANDLE_TRANSITION

# 通常処理を継続
ジャンプ CONTINUE_NORMAL

# ============================================================
# 状態遷移ハンドラ
# ============================================================

ラベル HANDLE_TRANSITION

# 解像度を上げる
読む transition_info
取り出す transition_magnitude

実行する increase.resolution = {
  "magnitude": {transition_magnitude}
}
入れる resolution_level
捨てる

# 詳細解析を実行
読む current_frame
読む resolution_level
実行する analyze.detailed
入れる detailed_result
捨てる

# 結果を記録
読む detailed_result
実行する record.transition_detail
捨てる

ジャンプ NEXT_FRAME

# ============================================================
# 通常処理
# ============================================================

ラベル CONTINUE_NORMAL

# 通常解析結果を記録
読む frame_result
実行する record.normal
捨てる

# ============================================================
# 次フレームへ
# ============================================================

ラベル NEXT_FRAME

# 現在フレームを前フレームとして保存
読む current_frame
入れる prev_frame
捨てる

# フレームインデックスを増加
読む frame_index
実行する counter.increment
入れる frame_index
捨てる

# 継続チェック
読む frame_index
実行する counter.check = {"max_count": 1000}
取り出す continue

条件ジャンプ PROCESS_FRAME

# ============================================================
# 完了
# ============================================================

ラベル END
```

## プロセッサ実装

### 1. 状態遷移検出プロセッサ

```python
def detect_transition(args: Dict[str, Any]) -> Dict[str, Any]:
    """状態遷移を検出"""
    frame_diff = args.get("frame_diff", {})

    # 各軸の変化量を取得
    axis_changes = frame_diff.get("axis_changes", {})

    # 総変化量
    total_change = sum(axis_changes.values())

    # 閾値判定
    is_transition = total_change > 0.1

    if total_change > 0.5:
        transition_type = "sudden"
    elif total_change > 0.3:
        transition_type = "moderate"
    elif total_change > 0.1:
        transition_type = "gradual"
    else:
        transition_type = "none"

    return {
        "is_transition": is_transition,
        "transition_magnitude": total_change,
        "transition_type": transition_type,
        "axis_changes": axis_changes
    }
```

### 2. 解像度更新プロセッサ

```python
def update_resolution(args: Dict[str, Any]) -> Dict[str, Any]:
    """解像度レベルを更新"""
    transition_info = args.get("transition_info", {})
    current_level = args.get("current_level", "low")

    if not transition_info.get("is_transition"):
        # 遷移なし → lowに戻す
        return {"new_level": "low"}

    magnitude = transition_info.get("transition_magnitude", 0.0)

    # 変化の大きさに応じて解像度を決定
    if magnitude > 0.5:
        new_level = "ultra"  # 1,000,000点
    elif magnitude > 0.3:
        new_level = "very_high"  # 500,000点
    elif magnitude > 0.1:
        new_level = "high"  # 200,000点
    else:
        new_level = "medium"  # 100,000点

    return {"new_level": new_level}
```

### 3. JCrossコード生成プロセッサ

```python
def generate_jcross_code(args: Dict[str, Any]) -> Dict[str, Any]:
    """現在の状態に応じてJCrossコードを生成"""
    state = args.get("current_state", {})

    generator = SelfModifyingJCrossGenerator()
    generated_code = generator.generate_code(state)

    return {"generated_code": generated_code}
```

### 4. JCrossコード実行プロセッサ

```python
def eval_jcross(args: Dict[str, Any]) -> Dict[str, Any]:
    """生成されたJCrossコードを実行"""
    code = args.get("generated_code", "")

    # JCrossコンパイラで実行
    # （実際の実装では、jcross_compilerを使用）

    return {"frame_result": result}
```

## 出力例

```
=============================================================
適応的動画解析結果
=============================================================
ファイル: screen_recording.mp4

フレーム 0 (0.00秒):
  解像度: low (50,000点)
  状態: 通常

フレーム 48 (1.60秒):
  解像度: low (50,000点)
  状態: 通常

フレーム 49 (1.63秒):
  ⚠️ 状態遷移検出！
  変化量: 0.52 (sudden)
  解像度を上げています: low → ultra (1,000,000点)

フレーム 50 (1.67秒):
  解像度: ultra (1,000,000点)
  状態: 詳細解析中
  検出領域数: 15

  領域 #00: (50, 30) 〜 (1870, 80)
    点数: 124,523 点（詳細）
    変化: 新規出現

  領域 #01: (100, 150) 〜 (800, 600)
    点数: 458,912 点（詳細）
    変化: 大幅変更

フレーム 55 (1.83秒):
  遷移完了検出
  解像度を戻しています: ultra → low (50,000点)

フレーム 56 (1.87秒):
  解像度: low (50,000点)
  状態: 通常
```

## 次のステップ

1. `adaptive_resolution_controller.py` - 適応的解像度コントローラ
2. `self_modifying_jcross.py` - JCross自己変容システム
3. `adaptive_processors.py` - 適応的解析用プロセッサ
4. `adaptive_video_analysis.jcross` - 自己変容型JCrossプログラム
5. `run_adaptive_analysis.py` - 適応的解析ランナー
