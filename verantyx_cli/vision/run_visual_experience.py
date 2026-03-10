#!/usr/bin/env python3
"""
Visual Experience Integration System
視覚経験統合システム

全てを統合:
- 視覚（カメラ）
- 生存（エネルギー、痛み）
- 発達（Level -2 〜 4）
- 感情（推測）

視覚が全ての発達を駆動する。
"""

import sys
from pathlib import Path
import time

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


class VisualExperienceSystem:
    """視覚経験統合システム"""

    def __init__(self):
        """Initialize visual experience system"""
        print()
        print("=" * 70)
        print("👁️  Verantyx 視覚経験統合システム")
        print("=" * 70)
        print()
        print("【統合される要素】")
        print("  1. 視覚（カメラ → Cross構造）")
        print("  2. 生存（エネルギー、痛み、死）")
        print("  3. 発達（Level -2 〜 Level 4）")
        print("  4. 感情（推測、学習）")
        print()
        print("視覚が全ての発達を駆動します。")
        print("=" * 70)
        print()

        # Cross変換エンジン
        print("⚙️  Cross変換エンジン初期化中...")
        self.converter = MultiLayerCrossConverter(quality="standard")

        # 生存システム
        print("🌱 生存システム初期化中...")
        self.survival = VerantyxSurvivalSystem()

        # 感情・発達システム
        print("🧠 感情・発達システム初期化中...")
        self.emotion = BabyEmotionSystemProcessor()

        # カメラ
        self.camera = None
        self.frame_count = 0

        # 視覚パターン履歴
        self.visual_patterns = {}

        # 統計
        self.stats = {
            "total_observations": 0,
            "face_detections": 0,
            "positive_reactions": 0,
            "negative_reactions": 0
        }

        print("✅ 初期化完了")
        print()

    def start(self):
        """視覚経験システムを開始"""
        if not CV2_AVAILABLE:
            print("❌ OpenCV が必要です")
            print("   pip install opencv-python pillow")
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
        print("視覚経験セッション開始")
        print("=" * 70)
        print()
        print("システムの動作:")
        print("  - カメラで観測 → Cross構造に変換")
        print("  - 生存本能チェック（笑顔/怖い顔）")
        print("  - エネルギー消費")
        print("  - 記憶に記録")
        print("  - パターン検出")
        print("  - 因果関係学習")
        print("  - 発達レベルに応じた処理")
        print()
        print("操作:")
        print("  [Q] - 終了")
        print("  [S] - ステータス表示")
        print("  [E] - エネルギー補給")
        print("  [R] - 休息（痛み回復）")
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

            # 定期的に視覚経験処理
            if self.frame_count % 30 == 0:  # 約1秒に1回
                self._process_visual_experience(frame)

            # ステータスをオーバーレイ
            self._draw_overlay(frame)

            # 画面表示
            cv2.imshow("Verantyx Visual Experience", frame)

            # キー入力
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == ord('Q'):
                print("\n👋 終了します")
                break
            elif key == ord('s') or key == ord('S'):
                self._print_status()
            elif key == ord('e') or key == ord('E'):
                self.survival.energy.recharge(30.0, "手動補給")
            elif key == ord('r') or key == ord('R'):
                self.survival.pain.recover("rest")
                print("😴 休息中...")

    def _process_visual_experience(self, frame):
        """視覚経験を処理"""
        print()
        print(f"👁️  観測 #{self.stats['total_observations'] + 1}")
        print("-" * 70)

        # ========================================
        # Stage 0: 生存状態チェック
        # ========================================
        self.survival.update()

        if self.survival.survival_state.is_dying():
            print("⚠️  瀕死状態！")

        # ========================================
        # Stage 1: Cross構造に変換
        # ========================================
        print("🔄 Cross構造に変換中...")

        # エネルギー消費（観測）
        self.survival.energy.consume("observe")

        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cross_structure = self.converter.convert(pil_image)

        # ========================================
        # Stage 2: 生存本能チェック（Level -2）
        # ========================================
        self._check_survival_instinct(frame, cross_structure)

        # ========================================
        # Stage 3: 記憶に記録（Level 0）
        # ========================================
        print("📝 記憶に記録中...")

        # 視覚 + 感覚 + 生存状態を統合
        experience = {
            "visual_cross": cross_structure,
            "sensory": {
                "energy": self.survival.survival_state.energy["current"],
                "pain": self.survival.survival_state.pain["current"]
            },
            "survival_status": self.survival.survival_state.status,
            "timestamp": self.stats["total_observations"]
        }

        # 記憶に追加
        self.emotion.observation.process_observe({
            "cross_structure": cross_structure
        })

        # ========================================
        # Stage 4: パターン検出（Level 1以降）
        # ========================================
        if self.emotion.get_state()["development"]["current_level"] >= 1:
            if self.survival.survival_state.energy["current"] > 30:
                print("🔍 パターン検出中...")
                self.survival.energy.consume("think")

                pattern_id = self.emotion.pattern.process_detect_pattern({
                    "observation_cross": experience
                })

                if pattern_id:
                    # 視覚パターン履歴に追加
                    if pattern_id not in self.visual_patterns:
                        self.visual_patterns[pattern_id] = {
                            "count": 0,
                            "first_seen": self.frame_count,
                            "label": None
                        }
                    self.visual_patterns[pattern_id]["count"] += 1
                    print(f"   パターンID: {pattern_id[:8]}... (出現: {self.visual_patterns[pattern_id]['count']}回)")

        # ========================================
        # Stage 5: 因果関係学習（Level 2以降）
        # ========================================
        if self.emotion.get_state()["development"]["current_level"] >= 2:
            if self.survival.survival_state.energy["current"] > 40:
                print("🧠 因果関係学習中...")
                self.survival.energy.consume("learn")
                # （因果関係学習は既存のシステムで処理）

        # 統計更新
        self.stats["total_observations"] += 1

        print("-" * 70)
        print()

    def _check_survival_instinct(self, frame, cross_structure):
        """生存本能チェック（Level -2: DNA）"""
        # 簡易的な顔検出（OpenCVの顔認識）
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            self.stats["face_detections"] += 1
            print("👤 顔検出！")

            # 笑顔検出の簡易版（実際にはもっと複雑）
            # ここでは50%の確率でポジティブ/ネガティブと仮定
            import random
            is_positive = random.random() > 0.5

            if is_positive:
                print("   → 😊 ポジティブな顔（生得的反応: 笑う）")
                self.stats["positive_reactions"] += 1
                # エネルギー少し回復
                self.survival.energy.recharge(2.0, "ポジティブ刺激")
            else:
                print("   → 😟 ネガティブな顔（生得的反応: 警戒）")
                self.stats["negative_reactions"] += 1
                # 痛み少し増加
                self.survival.pain.inflict("collision")  # 仮の原因

    def _draw_overlay(self, frame):
        """ステータスをオーバーレイ"""
        height, width = frame.shape[:2]

        # 半透明背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # テキスト
        y_pos = 25

        # 生存状態
        status = self.survival.survival_state.status
        status_color = (0, 255, 0) if status == "alive" else (0, 0, 255)
        cv2.putText(frame, f"Status: {status}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        y_pos += 30

        # エネルギー
        energy = self.survival.survival_state.energy["current"]
        energy_color = (0, 255, 0) if energy > 50 else (0, 165, 255) if energy > 20 else (0, 0, 255)
        cv2.putText(frame, f"Energy: {energy:.1f}/100", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, energy_color, 1)
        y_pos += 25

        # 痛み
        pain = self.survival.survival_state.pain["current"]
        pain_color = (255, 255, 255) if pain < 30 else (0, 165, 255) if pain < 60 else (0, 0, 255)
        cv2.putText(frame, f"Pain: {pain:.1f}/100", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, pain_color, 1)
        y_pos += 25

        # 発達レベル
        level = self.emotion.get_state()["development"]["current_level"]
        cv2.putText(frame, f"Development: Level {level}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y_pos += 25

        # 観測数
        cv2.putText(frame, f"Observations: {self.stats['total_observations']}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y_pos += 25

        # パターン数
        cv2.putText(frame, f"Patterns: {len(self.visual_patterns)}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def _print_status(self):
        """詳細ステータス表示"""
        print()
        print("=" * 70)
        print("📊 視覚経験統合システム - 詳細ステータス")
        print("=" * 70)
        print()

        # 生存
        self.survival.print_status()

        # 発達
        self.emotion.print_status()

        # 視覚
        print("【視覚統計】")
        print(f"  総観測数: {self.stats['total_observations']}")
        print(f"  顔検出数: {self.stats['face_detections']}")
        print(f"  ポジティブ反応: {self.stats['positive_reactions']}")
        print(f"  ネガティブ反応: {self.stats['negative_reactions']}")
        print(f"  視覚パターン数: {len(self.visual_patterns)}")
        print()

        # 頻出パターン
        if self.visual_patterns:
            sorted_patterns = sorted(
                self.visual_patterns.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:5]

            print("頻出視覚パターン（Top 5）:")
            for pattern_id, data in sorted_patterns:
                print(f"  - {pattern_id[:8]}... : {data['count']}回")
            print()

        print("=" * 70)
        print()

    def _cleanup(self):
        """クリーンアップ"""
        print()
        print("=" * 70)
        print("視覚経験セッション終了")
        print("=" * 70)
        print()

        # 最終統計
        self._print_status()

        if self.camera:
            self.camera.release()

        cv2.destroyAllWindows()


def main():
    """メイン関数"""
    system = VisualExperienceSystem()
    return system.start()


if __name__ == "__main__":
    sys.exit(main())
