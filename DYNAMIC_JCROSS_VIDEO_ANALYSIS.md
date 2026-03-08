# 動的JCrossコード生成による動画解析システム

## コンセプト

動画のフレーム間変化を**JCrossコードの動的変更**として表現し、
コードの変容を観察することで動画の「動き」を理解する。

### 従来のアプローチ（実装済み）
```
フレーム1 → Cross構造1
フレーム2 → Cross構造2
...
```

### 新しいアプローチ（これから実装）
```
フレーム1 → JCrossコードA
フレーム2 → JCrossコードAをBに変更（差分を動的生成）
フレーム3 → JCrossコードBをCに変更
...

変更履歴 → 別のCross層にマッピング
JCrossコードの変容 → 観察・レポート
```

## 全体フロー

```
動画 (video.mp4)
  ↓
【1】30fpsでフレーム分解（.jcross）
  ↓
【2】各フレームをCross構造に変換（.jcross）
  ↓
【3】フレーム間差分を検出（.jcross）
  ↓
【4】差分 → JCrossコード動的変更として表現（.jcross）
  ↓
【5】変更履歴を別のCross層にマッピング（.jcross）
  ↓
【6】JCrossコードの変容を観察（.jcross）
  ↓
【7】レポート生成（.jcross）
```

**重要**: 全て`.jcross`で実装。Pythonは入出力変換のみ。

## ARC-AGI2資産の活用

### 1. グリッド表現
```
ARC-AGI2のアプローチ:
- 画像 → N×Nグリッド（例: 32x32）
- 各セルに色インデックス（0-9の10色）
- パターン認識が容易

Verantyx Crossへの応用:
- フレーム → 32x32グリッド
- グリッド → Cross構造
- グリッドの変化 → JCrossコードの変更
```

### 2. パターン変換規則
```
ARC-AGI2の変換:
入力グリッド → 変換規則 → 出力グリッド

Verantyxの変換:
フレームN → 変換規則（JCrossコード） → フレームN+1

変換規則そのものをJCrossコードで表現！
```

### 3. 人間の脳のアプローチ
```
人間の視覚処理:
- フレーム全体を記憶するのではなく「変化」を記憶
- 予測と差分で世界を理解

Verantyxでの実装:
- ベースとなるJCrossコード（フレーム1）
- 変更差分のみを追加で記憶（フレーム2,3,...）
- 変更履歴がそのまま「動き」の理解
```

## 詳細設計

### 【1】30fpsフレーム分解（video_frame_extractor.jcross）

```jcross
# 動画フレーム抽出 - JCross実装

"🎬 動画をフレームに分解中..."
表示する

# 動画パスを取得
実行する io.get_video_path
入れる video_path
捨てる

# OpenCV経由でフレーム抽出
実行する video.extract_frames = {
  "path": video_path,
  "fps": 30,
  "max_frames": 900  # 30秒分
}
入れる frames_result
捨てる

取り出す frames_result
辞書から取り出す "frame_count"
入れる frame_count
捨てる

"✅ "
表示する
取り出す frame_count
表示する
" フレーム抽出完了"
表示する
""
表示する

# フレーム配列を保存
取り出す frames_result
辞書から取り出す "frames"
入れる frames
捨てる

# 次のステップへ
```

### 【2】フレーム → Cross構造変換（frame_to_cross.jcross）

```jcross
# フレーム → Cross構造変換

"📊 各フレームをCross構造に変換中..."
表示する

# フレーム配列を取得
取り出す frames
入れる current_frames
捨てる

# Cross構造配列を初期化
実行する cross.init_array
入れる cross_frames
捨てる

0
入れる frame_index
捨てる

ラベル CONVERT_FRAME
  # フレーム数チェック
  取り出す current_frames
  辞書から取り出す "length"
  0ならジャンプ CONVERT_DONE

  # 現在のフレームを取得
  取り出す current_frames
  取り出す frame_index
  辞書から取り出す
  入れる current_frame
  捨てる

  # フレーム → ARC-AGI2グリッド (32x32)
  取り出す current_frame
  実行する arc.frame_to_grid = {"size": 32}
  入れる grid
  捨てる

  # グリッド → Cross構造
  取り出す grid
  実行する cross.grid_to_cross
  入れる cross_structure
  捨てる

  # フレームインデックスを追加
  取り出す cross_structure
  取り出す frame_index
  辞書に追加 "frame_index"
  入れる cross_structure
  捨てる

  # Cross構造配列に追加
  取り出す cross_frames
  取り出す cross_structure
  実行する cross.array_append
  入れる cross_frames
  捨てる

  # 進捗表示
  取り出す frame_index
  1
  足す
  入れる frame_index
  捨てる

  # 次のフレームへ
  取り出す current_frames
  辞書から取り出す "rest"
  入れる current_frames
  捨てる

  ジャンプ CONVERT_FRAME

ラベル CONVERT_DONE

"✅ "
表示する
取り出す frame_index
表示する
" フレームを変換完了"
表示する
""
表示する
```

### 【3】フレーム間差分検出（frame_diff_detector.jcross）

```jcross
# フレーム間差分検出

"🔍 フレーム間の差分を検出中..."
表示する

# Cross構造配列を取得
取り出す cross_frames
入れる current_cross_frames
捨てる

# 差分配列を初期化
実行する cross.init_array
入れる diff_array
捨てる

# 前フレームを保存する変数
実行する cross.null
入れる prev_frame
捨てる

0
入れる diff_count
捨てる

ラベル DETECT_DIFF
  # フレーム数チェック
  取り出す current_cross_frames
  辞書から取り出す "length"
  0ならジャンプ DETECT_DONE

  # 現在のフレームを取得
  取り出す current_cross_frames
  辞書から取り出す "0"
  入れる current_frame
  捨てる

  # 前フレームが存在するかチェック
  取り出す prev_frame
  実行する cross.is_null
  入れる is_first_frame
  捨てる

  取り出す is_first_frame
  辞書から取り出す "result"
  1ならジャンプ SKIP_DIFF

  # 差分を計算
  取り出す prev_frame
  取り出す current_frame
  実行する cross.calculate_diff
  入れる diff
  捨てる

  # 差分が存在するかチェック
  取り出す diff
  辞書から取り出す "has_changes"
  0ならジャンプ SKIP_DIFF

  # 差分配列に追加
  取り出す diff_array
  取り出す diff
  実行する cross.array_append
  入れる diff_array
  捨てる

  # 差分カウント
  取り出す diff_count
  1
  足す
  入れる diff_count
  捨てる

  ラベル SKIP_DIFF

  # 現在フレームを前フレームとして保存
  取り出す current_frame
  入れる prev_frame
  捨てる

  # 次のフレームへ
  取り出す current_cross_frames
  辞書から取り出す "rest"
  入れる current_cross_frames
  捨てる

  ジャンプ DETECT_DIFF

ラベル DETECT_DONE

"✅ "
表示する
取り出す diff_count
表示する
" 個の差分を検出"
表示する
""
表示する
```

### 【4】差分 → JCrossコード動的生成（dynamic_code_generator.jcross）

**これが最も重要な部分！**

```jcross
# 差分 → JCrossコード動的生成

"⚡ フレーム差分からJCrossコードを動的生成中..."
表示する

# 差分配列を取得
取り出す diff_array
入れる current_diffs
捨てる

# ベースとなるJCrossコード（フレーム1）
実行する jcross.init_base_code
入れる base_code
捨てる

# JCrossコード変更履歴配列
実行する cross.init_array
入れる code_changes
捨てる

# 現在のコード
取り出す base_code
入れる current_code
捨てる

0
入れる change_index
捨てる

ラベル GENERATE_CODE
  # 差分数チェック
  取り出す current_diffs
  辞書から取り出す "length"
  0ならジャンプ GENERATE_DONE

  # 現在の差分を取得
  取り出す current_diffs
  辞書から取り出す "0"
  入れる diff
  捨てる

  # 差分の種類を判定
  取り出す diff
  実行する jcross.classify_diff_type
  入れる diff_type
  捨てる

  # 差分タイプに応じてJCrossコード変更を生成
  取り出す diff_type
  辞書から取り出す "type"
  入れる type_name
  捨てる

  # タイプ別分岐
  取り出す type_name
  "point_added"
  実行する cross.equals
  入れる is_point_added
  捨てる

  取り出す is_point_added
  辞書から取り出す "result"
  1ならジャンプ HANDLE_POINT_ADDED

  取り出す type_name
  "point_moved"
  実行する cross.equals
  入れる is_point_moved
  捨てる

  取り出す is_point_moved
  辞書から取り出す "result"
  1ならジャンプ HANDLE_POINT_MOVED

  取り出す type_name
  "point_removed"
  実行する cross.equals
  入れる is_point_removed
  捨てる

  取り出す is_point_removed
  辞書から取り出す "result"
  1ならジャンプ HANDLE_POINT_REMOVED

  # デフォルト: 色変化
  ジャンプ HANDLE_COLOR_CHANGED

  # ═══════════════════════════════════════════════════════════
  # 点追加: JCrossコードに点追加命令を挿入
  # ═══════════════════════════════════════════════════════════
  ラベル HANDLE_POINT_ADDED
    取り出す diff
    取り出す current_code
    実行する jcross.add_point_instruction
    入れる new_code
    捨てる

    # コード変更を記録
    "ADDED_POINT"
    入れる change_type
    捨てる

    ジャンプ RECORD_CHANGE

  # ═══════════════════════════════════════════════════════════
  # 点移動: JCrossコードに移動命令を挿入
  # ═══════════════════════════════════════════════════════════
  ラベル HANDLE_POINT_MOVED
    取り出す diff
    取り出す current_code
    実行する jcross.add_move_instruction
    入れる new_code
    捨てる

    "MOVED_POINT"
    入れる change_type
    捨てる

    ジャンプ RECORD_CHANGE

  # ═══════════════════════════════════════════════════════════
  # 点削除: JCrossコードから削除命令を挿入
  # ═══════════════════════════════════════════════════════════
  ラベル HANDLE_POINT_REMOVED
    取り出す diff
    取り出す current_code
    実行する jcross.add_remove_instruction
    入れる new_code
    捨てる

    "REMOVED_POINT"
    入れる change_type
    捨てる

    ジャンプ RECORD_CHANGE

  # ═══════════════════════════════════════════════════════════
  # 色変化: JCrossコードの色値を変更
  # ═══════════════════════════════════════════════════════════
  ラベル HANDLE_COLOR_CHANGED
    取り出す diff
    取り出す current_code
    実行する jcross.update_color_value
    入れる new_code
    捨てる

    "CHANGED_COLOR"
    入れる change_type
    捨てる

  # ═══════════════════════════════════════════════════════════
  # コード変更を記録
  # ═══════════════════════════════════════════════════════════
  ラベル RECORD_CHANGE
    # 変更前後のコード差分を計算
    取り出す current_code
    取り出す new_code
    実行する jcross.code_diff
    入れる code_diff
    捨てる

    # 変更レコードを作成
    実行する cross.create_dict
    入れる change_record
    捨てる

    取り出す change_record
    取り出す change_index
    辞書に追加 "index"
    取り出す change_type
    辞書に追加 "type"
    取り出す code_diff
    辞書に追加 "code_diff"
    取り出す diff
    辞書に追加 "source_diff"
    入れる change_record
    捨てる

    # 変更履歴に追加
    取り出す code_changes
    取り出す change_record
    実行する cross.array_append
    入れる code_changes
    捨てる

    # 現在のコードを更新
    取り出す new_code
    入れる current_code
    捨てる

    # インデックス更新
    取り出す change_index
    1
    足す
    入れる change_index
    捨てる

  # 次の差分へ
  取り出す current_diffs
  辞書から取り出す "rest"
  入れる current_diffs
  捨てる

  ジャンプ GENERATE_CODE

ラベル GENERATE_DONE

"✅ "
表示する
取り出す change_index
表示する
" 個のJCrossコード変更を生成"
表示する
""
表示する
```

### 【5】変更履歴 → Cross層マッピング（change_to_cross_layer.jcross）

```jcross
# 変更履歴を別のCross層にマッピング

"🗺️  コード変更履歴をCross層にマッピング中..."
表示する

# コード変更履歴を取得
取り出す code_changes
入れる current_changes
捨てる

# Cross層を初期化（6軸+TIME軸）
実行する cross.init_layer = {
  "axes": ["FRONT", "BACK", "UP", "DOWN", "RIGHT", "LEFT", "TIME"],
  "type": "code_change_history"
}
入れる change_layer
捨てる

0
入れる mapped_count
捨てる

ラベル MAP_CHANGE
  # 変更数チェック
  取り出す current_changes
  辞書から取り出す "length"
  0ならジャンプ MAP_DONE

  # 現在の変更を取得
  取り出す current_changes
  辞書から取り出す "0"
  入れる change
  捨てる

  # 変更タイプに応じてCross軸を決定
  取り出す change
  辞書から取り出す "type"
  入れる change_type
  捨てる

  # ADDED_POINT → FRONT軸（前方への追加）
  取り出す change_type
  "ADDED_POINT"
  実行する cross.equals
  入れる is_added
  捨てる

  取り出す is_added
  辞書から取り出す "result"
  1ならジャンプ MAP_TO_FRONT

  # REMOVED_POINT → BACK軸（後方への削除）
  取り出す change_type
  "REMOVED_POINT"
  実行する cross.equals
  入れる is_removed
  捨てる

  取り出す is_removed
  辞書から取り出す "result"
  1ならジャンプ MAP_TO_BACK

  # MOVED_POINT → RIGHT/LEFT軸（移動）
  取り出す change_type
  "MOVED_POINT"
  実行する cross.equals
  入れる is_moved
  捨てる

  取り出す is_moved
  辞書から取り出す "result"
  1ならジャンプ MAP_TO_RIGHT_LEFT

  # CHANGED_COLOR → UP/DOWN軸（属性変化）
  ジャンプ MAP_TO_UP_DOWN

  # ═══════════════════════════════════════════════════════════
  # FRONT軸にマッピング
  # ═══════════════════════════════════════════════════════════
  ラベル MAP_TO_FRONT
    取り出す change_layer
    "FRONT"
    取り出す change
    実行する cross.add_to_axis
    入れる change_layer
    捨てる

    ジャンプ MAP_NEXT

  # ═══════════════════════════════════════════════════════════
  # BACK軸にマッピング
  # ═══════════════════════════════════════════════════════════
  ラベル MAP_TO_BACK
    取り出す change_layer
    "BACK"
    取り出す change
    実行する cross.add_to_axis
    入れる change_layer
    捨てる

    ジャンプ MAP_NEXT

  # ═══════════════════════════════════════════════════════════
  # RIGHT/LEFT軸にマッピング
  # ═══════════════════════════════════════════════════════════
  ラベル MAP_TO_RIGHT_LEFT
    # 移動方向を判定
    取り出す change
    実行する cross.get_move_direction
    入れる direction
    捨てる

    取り出す direction
    辞書から取り出す "axis"
    入れる target_axis
    捨てる

    取り出す change_layer
    取り出す target_axis
    取り出す change
    実行する cross.add_to_axis
    入れる change_layer
    捨てる

    ジャンプ MAP_NEXT

  # ═══════════════════════════════════════════════════════════
  # UP/DOWN軸にマッピング
  # ═══════════════════════════════════════════════════════════
  ラベル MAP_TO_UP_DOWN
    取り出す change_layer
    "UP"
    取り出す change
    実行する cross.add_to_axis
    入れる change_layer
    捨てる

  # ═══════════════════════════════════════════════════════════
  # 次の変更へ
  # ═══════════════════════════════════════════════════════════
  ラベル MAP_NEXT
    取り出す mapped_count
    1
    足す
    入れる mapped_count
    捨てる

    取り出す current_changes
    辞書から取り出す "rest"
    入れる current_changes
    捨てる

    ジャンプ MAP_CHANGE

ラベル MAP_DONE

"✅ "
表示する
取り出す mapped_count
表示する
" 個の変更をCross層にマッピング完了"
表示する
""
表示する
```

### 【6】JCrossコード変容の観察（code_evolution_observer.jcross）

```jcross
# JCrossコードの変容を観察

"👁️  JCrossコードの変容を観察中..."
表示する

# Cross層を取得
取り出す change_layer
入れる layer
捨てる

# 観察結果を初期化
実行する cross.create_dict
入れる observations
捨てる

# ═══════════════════════════════════════════════════════════
# 各軸の変化パターンを観察
# ═══════════════════════════════════════════════════════════

# FRONT軸（追加）の観察
取り出す layer
"FRONT"
実行する cross.get_axis
入れる front_changes
捨てる

取り出す front_changes
実行する cross.analyze_pattern
入れる front_pattern
捨てる

取り出す observations
"FRONT_pattern"
取り出す front_pattern
辞書に追加
入れる observations
捨てる

# BACK軸（削除）の観察
取り出す layer
"BACK"
実行する cross.get_axis
入れる back_changes
捨てる

取り出す back_changes
実行する cross.analyze_pattern
入れる back_pattern
捨てる

取り出す observations
"BACK_pattern"
取り出す back_pattern
辞書に追加
入れる observations
捨てる

# RIGHT/LEFT軸（移動）の観察
取り出す layer
"RIGHT"
実行する cross.get_axis
入れる right_changes
捨てる

取り出す layer
"LEFT"
実行する cross.get_axis
入れる left_changes
捨てる

取り出す right_changes
取り出す left_changes
実行する cross.analyze_movement_pattern
入れる movement_pattern
捨てる

取り出す observations
"MOVEMENT_pattern"
取り出す movement_pattern
辞書に追加
入れる observations
捨てる

# UP/DOWN軸（属性変化）の観察
取り出す layer
"UP"
実行する cross.get_axis
入れる up_changes
捨てる

取り出す up_changes
実行する cross.analyze_attribute_pattern
入れる attribute_pattern
捨てる

取り出す observations
"ATTRIBUTE_pattern"
取り出す attribute_pattern
辞書に追加
入れる observations
捨てる

# ═══════════════════════════════════════════════════════════
# 時系列パターンの観察
# ═══════════════════════════════════════════════════════════

取り出す layer
実行する cross.analyze_temporal_pattern
入れる temporal_pattern
捨てる

取り出す observations
"TEMPORAL_pattern"
取り出す temporal_pattern
辞書に追加
入れる observations
捨てる

# ═══════════════════════════════════════════════════════════
# コード複雑度の変化を観察
# ═══════════════════════════════════════════════════════════

取り出す code_changes
実行する jcross.analyze_complexity_evolution
入れる complexity_evolution
捨てる

取り出す observations
"COMPLEXITY_evolution"
取り出す complexity_evolution
辞書に追加
入れる observations
捨てる

"✅ 観察完了"
表示する
""
表示する
```

### 【7】レポート生成（evolution_reporter.jcross）

```jcross
# JCrossコード変容レポート生成

"📝 レポートを生成中..."
表示する

# 観察結果を取得
取り出す observations
入れる obs
捨てる

# レポート文字列を構築
""
入れる report
捨てる

# ═══════════════════════════════════════════════════════════
# ヘッダー
# ═══════════════════════════════════════════════════════════

取り出す report
"# JCrossコード変容レポート\n\n"
実行する cross.string_concat
入れる report
捨てる

取り出す report
"動画のフレーム間変化をJCrossコードの動的変更として解析\n\n"
実行する cross.string_concat
入れる report
捨てる

# ═══════════════════════════════════════════════════════════
# 1. 全体統計
# ═══════════════════════════════════════════════════════════

取り出す report
"## 1. 全体統計\n\n"
実行する cross.string_concat
入れる report
捨てる

# フレーム数
取り出す report
"- 総フレーム数: "
実行する cross.string_concat
取り出す frame_count
実行する cross.to_string
実行する cross.string_concat
"\n"
実行する cross.string_concat
入れる report
捨てる

# コード変更数
取り出す report
"- JCrossコード変更数: "
実行する cross.string_concat
取り出す code_changes
実行する cross.array_length
実行する cross.to_string
実行する cross.string_concat
"\n\n"
実行する cross.string_concat
入れる report
捨てる

# ═══════════════════════════════════════════════════════════
# 2. Cross軸別の変化パターン
# ═══════════════════════════════════════════════════════════

取り出す report
"## 2. Cross軸別の変化パターン\n\n"
実行する cross.string_concat
入れる report
捨てる

# FRONT軸（追加）
取り出す report
"### FRONT軸（点の追加）\n"
実行する cross.string_concat
入れる report
捨てる

取り出す obs
"FRONT_pattern"
辞書から取り出す
実行する cross.pattern_to_string
実行する cross.string_concat
"\n"
実行する cross.string_concat
入れる report
捨てる

# BACK軸（削除）
取り出す report
"### BACK軸（点の削除）\n"
実行する cross.string_concat
入れる report
捨てる

取り出す obs
"BACK_pattern"
辞書から取り出す
実行する cross.pattern_to_string
実行する cross.string_concat
"\n"
実行する cross.string_concat
入れる report
捨てる

# RIGHT/LEFT軸（移動）
取り出す report
"### RIGHT/LEFT軸（点の移動）\n"
実行する cross.string_concat
入れる report
捨てる

取り出す obs
"MOVEMENT_pattern"
辞書から取り出す
実行する cross.pattern_to_string
実行する cross.string_concat
"\n"
実行する cross.string_concat
入れる report
捨てる

# UP/DOWN軸（属性変化）
取り出す report
"### UP/DOWN軸（属性変化）\n"
実行する cross.string_concat
入れる report
捨てる

取り出す obs
"ATTRIBUTE_pattern"
辞書から取り出す
実行する cross.pattern_to_string
実行する cross.string_concat
"\n\n"
実行する cross.string_concat
入れる report
捨てる

# ═══════════════════════════════════════════════════════════
# 3. 時系列パターン
# ═══════════════════════════════════════════════════════════

取り出す report
"## 3. 時系列パターン\n\n"
実行する cross.string_concat
入れる report
捨てる

取り出す obs
"TEMPORAL_pattern"
辞書から取り出す
実行する cross.temporal_pattern_to_string
実行する cross.string_concat
"\n\n"
実行する cross.string_concat
入れる report
捨てる

# ═══════════════════════════════════════════════════════════
# 4. コード複雑度の変化
# ═══════════════════════════════════════════════════════════

取り出す report
"## 4. JCrossコード複雑度の変化\n\n"
実行する cross.string_concat
入れる report
捨てる

取り出す obs
"COMPLEXITY_evolution"
辞書から取り出す
実行する cross.complexity_to_string
実行する cross.string_concat
"\n\n"
実行する cross.string_concat
入れる report
捨てる

# ═══════════════════════════════════════════════════════════
# 5. 動きの解釈
# ═══════════════════════════════════════════════════════════

取り出す report
"## 5. 動きの解釈\n\n"
実行する cross.string_concat
入れる report
捨てる

取り出す obs
実行する jcross.interpret_motion
入れる interpretation
捨てる

取り出す report
取り出す interpretation
実行する cross.string_concat
"\n\n"
実行する cross.string_concat
入れる report
捨てる

# ═══════════════════════════════════════════════════════════
# レポートを保存
# ═══════════════════════════════════════════════════════════

取り出す report
実行する io.save_report = {"filename": "jcross_evolution_report.md"}
捨てる

"✅ レポート生成完了: jcross_evolution_report.md"
表示する
""
表示する

終わる
```

## Pythonプロセッサ（最小限）

Pythonは入出力変換のみ：

```python
# verantyx_cli/vision/dynamic_jcross_processors.py

def extract_frames(args):
    """OpenCV経由でフレーム抽出（Pythonのみ）"""
    import cv2
    path = args.get("path")
    fps = args.get("fps", 30)
    max_frames = args.get("max_frames", 900)

    cap = cv2.VideoCapture(path)
    frames = []

    # フレーム抽出
    # ...

    return {"frames": frames, "frame_count": len(frames)}


def frame_to_grid(args):
    """フレーム → ARC-AGI2グリッド（32x32、10色）"""
    frame = args.get("frame")
    size = args.get("size", 32)

    # リサイズ
    # 10色に量子化
    # ...

    return {"grid": grid_array}
```

## まとめ

このアーキテクチャにより：

✅ **動画の変化 = JCrossコードの動的変更**
✅ **ARC-AGI2の資産（グリッド表現）を最大活用**
✅ **全て`.jcross`で実装**（Pythonは入出力のみ）
✅ **変更履歴をCross層にマッピング**
✅ **コードの変容を観察 → レポート生成**
✅ **人間の脳のアプローチ（差分記憶）を模倣**

## 実装状況

### ✅ 実装完了

#### 1. 基本実装 (`dynamic_video_analysis.jcross`)
- フレーム抽出（30fps）
- ARC-AGI2グリッド変換（32x32、10色）
- Cross構造変換
- フレーム間差分検出
- 基本レポート生成

#### 2. フル実装 (`dynamic_video_analysis_full.jcross`)
- **JCrossコード動的生成**（完全実装）
  - 点追加命令生成
  - 点移動命令生成
  - 点削除命令生成
  - 色変更命令生成
- **Cross層マッピング**
  - FRONT軸: 追加命令
  - BACK軸: 削除命令
  - UP/DOWN軸: 属性変化
  - RIGHT/LEFT軸: 移動
- **コード変容観察**
  - 各軸のパターン解析
  - 変化頻度の計測
- **詳細レポート生成**
  - 全体統計
  - Cross軸別パターン
  - JCrossコード変更詳細
  - Cross層マッピング結果

#### 3. Pythonプロセッサ (`dynamic_jcross_processors.py`)
- `extract_frames`: フレーム抽出（OpenCV）
- `frame_to_grid`: ARC-AGI2グリッド変換
- `grid_to_cross`: Cross構造変換
- `calculate_diff`: 差分検出
- `classify_diff_type`: 差分分類
- `add_point_instruction`: 点追加JCrossコード生成
- `add_move_instruction`: 移動JCrossコード生成
- `add_remove_instruction`: 削除JCrossコード生成
- `update_color_value`: 色変更JCrossコード生成
- `code_diff`: コード差分計算
- `analyze_pattern`: パターン解析

#### 4. ランナー
- `run_dynamic_video_analysis.py`: 基本版ランナー
- `run_dynamic_full.py`: フル実装版ランナー（レポート保存機能付き）

### 使い方

#### 基本版
```bash
python -m verantyx_cli.vision.run_dynamic_video_analysis video.mp4
```

#### フル実装版
```bash
python -m verantyx_cli.vision.run_dynamic_full video.mp4 --save-report report.json
```

### 出力例（フル実装版）

```
🎬 Dynamic JCross Video Analysis - Full Implementation
============================================================

## 1. 全体統計
- 総フレーム数: 300
- 差分検出数: 245
- JCrossコード変更数: 245
- Cross層へのマッピング数: 245

## 2. Cross軸別の変化パターン

### FRONT軸（点の追加）
- パターン: high_frequency
- 頻度: 154 回

### BACK軸（点の削除）
- パターン: high_frequency
- 頻度: 139 回

## 3. JCrossコード動的変更の詳細

### ベースコード（フレーム1）
```jcross
# Base JCross Code - Frame 1
# 動的に生成されたコード

実行する cross.init_frame
入れる frame
捨てる
```

### 変更履歴
- FRONT軸（追加命令）: 154 箇所
- BACK軸（削除命令）: 139 箇所

## 4. Cross層マッピング結果

変更履歴を6軸Cross層にマッピングしました:
- FRONT軸: 前方への追加（新しい点の出現）
- BACK軸: 後方への削除（点の消失）
- UP/DOWN軸: 属性変化（色の変化）
- RIGHT/LEFT軸: 横方向移動
- TIME軸: 時系列情報
```
