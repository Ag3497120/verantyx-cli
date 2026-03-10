#!/usr/bin/env python3
"""
Visual Learning System
視覚学習システム

シミュレーションではなく、実際に学習する。

学習の流れ:
1. 視覚パターンを観測
2. 人間がラベルを教える
3. パターンとラベルを記憶
4. 因果関係を学習
5. 次回から自動認識
"""

import sys
from pathlib import Path
import time
import json

try:
    import cv2
    import numpy as np
    from PIL import Image
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter
from verantyx_cli.vision.baby_emotion_processors import BabyEmotionSystemProcessor
from verantyx_cli.vision.verantyx_survival_processors import VerantyxSurvivalSystem


class VisualLearningSystem:
    """視覚学習システム（実際に学習する）"""

    def __init__(self, learning_db_path: Path = None):
        """
        Initialize visual learning system

        Args:
            learning_db_path: 学習データベースのパス
        """
        print()
        print("=" * 70)
        print("🎓 Verantyx 視覚学習システム")
        print("=" * 70)
        print()
        print("【実際の学習】")
        print("  - カメラで観測")
        print("  - 人間がラベルを教える")
        print("  - パターンを記憶")
        print("  - 因果関係を学習")
        print("  - 次回から自動認識")
        print()
        print("シミュレーションではなく、本物の学習です。")
        print("=" * 70)
        print()

        # 学習データベースのパス
        if learning_db_path is None:
            learning_db_path = Path.home() / ".verantyx" / "visual_learning.json"
        self.learning_db_path = learning_db_path

        # Cross変換エンジン
        print("⚙️  Cross変換エンジン初期化中...")
        self.converter = MultiLayerCrossConverter(quality="standard")

        # 生存システム
        print("🌱 生存システム初期化中...")
        self.survival = VerantyxSurvivalSystem()

        # 感情・発達システム
        print("🧠 感情・発達システム初期化中...")
        self.emotion = BabyEmotionSystemProcessor()

        # 学習データベース
        self.learning_db = {
            "patterns": {},  # pattern_id -> {"label": str, "cross": dict, "examples": []}
            "causality": [], # [{"pattern": str, "action": str, "result": str, "count": int}]
            "statistics": {
                "total_learned": 0,
                "total_recognized": 0,
                "recognition_accuracy": 0.0
            }
        }

        # 既存の学習データを読み込み
        self._load_learning_db()

        # カメラ
        self.camera = None
        self.frame_count = 0

        # 学習モード
        self.learning_mode = "observe"  # observe, teach, recognize

        # 現在のフレームとCross構造
        self.current_frame = None
        self.current_cross = None
        self.current_pattern_id = None

        print("✅ 初期化完了")
        print()

    def _load_learning_db(self):
        """学習データベースを読み込み"""
        if self.learning_db_path.exists():
            with open(self.learning_db_path, 'r', encoding='utf-8') as f:
                self.learning_db = json.load(f)
            print(f"📂 学習データベースを読み込みました:")
            print(f"   学習済みパターン: {len(self.learning_db['patterns'])}")
            print(f"   因果関係: {len(self.learning_db['causality'])}")
            print()

    def _save_learning_db(self):
        """学習データベースを保存"""
        self.learning_db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.learning_db_path, 'w', encoding='utf-8') as f:
            json.dump(self.learning_db, f, indent=2, ensure_ascii=False)
        print(f"💾 学習データベースを保存しました")

    def start(self):
        """学習システムを開始"""
        if not CV2_AVAILABLE:
            print("❌ OpenCV が必要です")
            return 1

        # カメラを開く
        print("📷 カメラ起動中...")
        self.camera = cv2.VideoCapture(0)

        if not self.camera.isOpened():
            print("❌ カメラを開けませんでした")
            return 1

        # 解像度設定
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print()
        print("=" * 70)
        print("視覚学習セッション開始")
        print("=" * 70)
        print()
        print("【モード】")
        print("  1. 観測モード（observe）: ただ見るだけ")
        print("  2. 学習モード（teach）: 人間が教える")
        print("  3. 認識モード（recognize）: 学習したものを認識")
        print()
        print("【操作】")
        print("  [Space] - キャプチャ（観測モード → 学習モードへ）")
        print("  [R] - 認識モード切り替え")
        print("  [O] - 観測モード切り替え")
        print("  [S] - ステータス表示")
        print("  [E] - エネルギー補給")
        print("  [Q] - 終了")
        print()
        print("=" * 70)
        print()

        try:
            self._main_loop()
        finally:
            self._cleanup()

        return 0

    def _main_loop(self):
        """メインループ"""
        while True:
            # 生存チェック
            if self.survival.survival_state.is_dead():
                print()
                print("💀 システム停止（死亡）")
                break

            ret, frame = self.camera.read()
            if not ret:
                print("❌ フレーム取得失敗")
                break

            self.frame_count += 1
            self.current_frame = frame

            # 認識モードの場合、自動認識
            if self.learning_mode == "recognize" and self.frame_count % 30 == 0:
                self._auto_recognize()

            # 画面表示
            self._draw_ui(frame)
            cv2.imshow("Verantyx Visual Learning", frame)

            # キー入力
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == ord('Q'):
                print("\n👋 終了します")
                break
            elif key == ord(' '):  # Space
                self._capture_and_teach()
            elif key == ord('r') or key == ord('R'):
                self.learning_mode = "recognize"
                print("\n🔍 認識モードに切り替え")
            elif key == ord('o') or key == ord('O'):
                self.learning_mode = "observe"
                print("\n👁️  観測モードに切り替え")
            elif key == ord('s') or key == ord('S'):
                self._print_status()
            elif key == ord('e') or key == ord('E'):
                self.survival.energy.recharge(30.0, "手動補給")

            # 生存システム更新
            self.survival.update()

    def _capture_and_teach(self):
        """キャプチャして学習"""
        print()
        print("=" * 70)
        print("📸 キャプチャ - 学習モード")
        print("=" * 70)
        print()

        # Cross構造に変換
        print("🔄 Cross構造に変換中...")
        self.survival.energy.consume("observe")

        pil_image = Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB))
        self.current_cross = self.converter.convert(pil_image)

        # パターンIDを生成
        print("🔍 パターンを検出中...")
        self.survival.energy.consume("think")

        observation = {
            "cross_structure": self.current_cross,
            "sensory_params": {}
        }

        self.current_pattern_id = self.emotion.pattern.process_detect_pattern({
            "observation_cross": observation
        })

        print(f"   パターンID: {self.current_pattern_id[:16]}...")
        print()

        # 既存の学習データをチェック
        if self.current_pattern_id in self.learning_db["patterns"]:
            learned = self.learning_db["patterns"][self.current_pattern_id]
            print(f"✅ このパターンは学習済みです: 「{learned['label']}」")
            print(f"   学習回数: {len(learned['examples'])} 回")
            print()

            # 追加学習するか確認
            print("追加学習しますか？")
            print("  [Y] - はい（同じラベルで追加学習）")
            print("  [N] - いいえ")
            choice = input("選択: ").strip().lower()

            if choice == 'y':
                self._add_example(self.current_pattern_id, learned['label'])
            else:
                print("学習をスキップしました")
        else:
            # 新規学習
            print("❓ これは何ですか？")
            print()
            print("以下から選択、または新しいラベルを入力:")
            print("  1. smile (笑顔)")
            print("  2. scary_face (怖い顔)")
            print("  3. neutral_face (無表情)")
            print("  4. object (物体)")
            print("  または任意のラベルを入力")
            print()

            label_input = input("ラベル: ").strip()

            # 数字入力の場合
            label_map = {
                "1": "smile",
                "2": "scary_face",
                "3": "neutral_face",
                "4": "object"
            }

            label = label_map.get(label_input, label_input)

            if label:
                self._learn_new_pattern(self.current_pattern_id, label)
            else:
                print("ラベルが入力されませんでした")

        print()
        print("=" * 70)
        print()

    def _learn_new_pattern(self, pattern_id: str, label: str):
        """新しいパターンを学習"""
        print(f"\n📚 学習中: '{label}'")

        # パターンを保存
        self.learning_db["patterns"][pattern_id] = {
            "label": label,
            "cross_summary": self._summarize_cross(self.current_cross),
            "examples": [
                {
                    "timestamp": self.frame_count,
                    "energy": self.survival.survival_state.energy["current"]
                }
            ]
        }

        # Level 3: 言語獲得
        if self.emotion.get_state()["development"]["current_level"] >= 3:
            self.emotion.language.process_learn_label({
                "pattern_id": pattern_id,
                "label": label
            })

        # 感情の色を推測（Level 4）
        if self.emotion.get_state()["development"]["current_level"] >= 4:
            emotional_color = self._infer_emotional_color(label)
            self.emotion.concept.process_form_concept({
                "label": label,
                "emotional_color": emotional_color
            })

        # 統計更新
        self.learning_db["statistics"]["total_learned"] += 1

        # 保存
        self._save_learning_db()

        print(f"✅ 学習完了: '{label}'")
        print(f"   パターンID: {pattern_id[:16]}...")

    def _add_example(self, pattern_id: str, label: str):
        """既存パターンに例を追加"""
        self.learning_db["patterns"][pattern_id]["examples"].append({
            "timestamp": self.frame_count,
            "energy": self.survival.survival_state.energy["current"]
        })

        print(f"✅ 追加学習完了: '{label}'")
        print(f"   学習回数: {len(self.learning_db['patterns'][pattern_id]['examples'])} 回")

        self._save_learning_db()

    def _auto_recognize(self):
        """自動認識"""
        print(f"\n🔍 認識中... (フレーム {self.frame_count})")

        # Cross構造に変換
        self.survival.energy.consume("observe")

        pil_image = Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB))
        cross_structure = self.converter.convert(pil_image)

        # パターンIDを生成
        self.survival.energy.consume("think")

        observation = {
            "cross_structure": cross_structure,
            "sensory_params": {}
        }

        pattern_id = self.emotion.pattern.process_detect_pattern({
            "observation_cross": observation
        })

        # 学習データベースから検索
        if pattern_id in self.learning_db["patterns"]:
            learned = self.learning_db["patterns"][pattern_id]
            label = learned["label"]
            confidence = self._calculate_confidence(pattern_id, cross_structure)

            print(f"✅ 認識: 「{label}」 ({confidence:.1f}%)")

            # 統計更新
            self.learning_db["statistics"]["total_recognized"] += 1

            # 生存本能反応
            self._survival_reaction(label)

            return label, confidence
        else:
            print("❓ 未知のパターン（学習していません）")
            return None, 0.0

    def _survival_reaction(self, label: str):
        """ラベルに基づいた生存本能反応"""
        if label == "smile":
            print("   → 😊 ポジティブ反応（エネルギー回復）")
            self.survival.energy.recharge(5.0, "笑顔検出")
        elif label == "scary_face":
            print("   → 😰 ネガティブ反応（痛み増加）")
            self.survival.pain.inflict("collision")

    def _summarize_cross(self, cross_structure: dict) -> dict:
        """Cross構造を要約（保存用）"""
        if "layers" in cross_structure:
            return {
                "type": "multi_layer",
                "num_layers": len(cross_structure["layers"]),
                "total_points": cross_structure["metadata"]["total_points"]
            }
        else:
            return {
                "type": "single_layer"
            }

    def _infer_emotional_color(self, label: str) -> dict:
        """ラベルから感情の色を推測"""
        # 簡易的な推測
        if "smile" in label.lower():
            return {
                "pleasant": 0.8,
                "arousal": 0.6,
                "valence": 0.7,
                "description": "見ると嬉しいもの"
            }
        elif "scary" in label.lower():
            return {
                "pleasant": 0.2,
                "arousal": 0.8,
                "valence": -0.7,
                "description": "見ると怖いもの"
            }
        else:
            return {
                "pleasant": 0.5,
                "arousal": 0.5,
                "valence": 0.0,
                "description": "中立的なもの"
            }

    def _calculate_confidence(self, pattern_id: str, cross_structure: dict) -> float:
        """認識の確信度を計算"""
        # 簡易版: 学習回数に基づく
        examples = len(self.learning_db["patterns"][pattern_id]["examples"])
        confidence = min(95.0, 50.0 + (examples * 15.0))
        return confidence

    def _draw_ui(self, frame):
        """UIを描画"""
        height, width = frame.shape[:2]

        # 半透明背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 250), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        y_pos = 25

        # モード表示
        mode_text = f"Mode: {self.learning_mode.upper()}"
        mode_color = (0, 255, 0) if self.learning_mode == "recognize" else (255, 255, 0) if self.learning_mode == "teach" else (200, 200, 200)
        cv2.putText(frame, mode_text, (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
        y_pos += 35

        # 生存状態
        status = self.survival.survival_state.status
        status_color = (0, 255, 0) if status == "alive" else (0, 0, 255)
        cv2.putText(frame, f"Status: {status}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1)
        y_pos += 25

        # エネルギー
        energy = self.survival.survival_state.energy["current"]
        cv2.putText(frame, f"Energy: {energy:.1f}/100", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y_pos += 25

        # 発達レベル
        level = self.emotion.get_state()["development"]["current_level"]
        cv2.putText(frame, f"Level: {level}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y_pos += 25

        # 学習統計
        learned = len(self.learning_db["patterns"])
        cv2.putText(frame, f"Learned: {learned} patterns", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y_pos += 25

        recognized = self.learning_db["statistics"]["total_recognized"]
        cv2.putText(frame, f"Recognized: {recognized} times", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y_pos += 30

        # 操作説明
        cv2.putText(frame, "[Space] Capture  [R] Recognize  [O] Observe  [Q] Quit", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

    def _print_status(self):
        """詳細ステータス表示"""
        print()
        print("=" * 70)
        print("📊 視覚学習システム - 詳細ステータス")
        print("=" * 70)
        print()

        # 学習データベース
        print("【学習データベース】")
        print(f"  学習済みパターン: {len(self.learning_db['patterns'])}")
        print(f"  総学習回数: {self.learning_db['statistics']['total_learned']}")
        print(f"  総認識回数: {self.learning_db['statistics']['total_recognized']}")
        print()

        if self.learning_db["patterns"]:
            print("学習済みパターン:")
            for pattern_id, data in list(self.learning_db["patterns"].items())[:10]:
                label = data["label"]
                count = len(data["examples"])
                print(f"  - {pattern_id[:16]}... : 「{label}」 ({count}回)")
            print()

        # 生存
        self.survival.print_status()

        # 発達
        self.emotion.print_status()

        print("=" * 70)
        print()

    def _cleanup(self):
        """クリーンアップ"""
        print()
        print("=" * 70)
        print("視覚学習セッション終了")
        print("=" * 70)
        print()

        # 最終保存
        self._save_learning_db()

        # 最終統計
        self._print_status()

        if self.camera:
            self.camera.release()

        cv2.destroyAllWindows()


def main():
    """メイン関数"""
    system = VisualLearningSystem()
    return system.start()


if __name__ == "__main__":
    sys.exit(main())
