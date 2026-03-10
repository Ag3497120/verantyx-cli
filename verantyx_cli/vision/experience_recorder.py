#!/usr/bin/env python3
"""
Experience Recorder - 経験記録プログラム
Autonomous Emotion Inference System

ラベルなし。システム自身が観測し、推測し、感情を形成する。

使い方:
    python -m verantyx_cli.vision.experience_recorder
"""

import sys
from pathlib import Path
from typing import Optional
import argparse

try:
    import cv2
    import numpy as np
    from PIL import Image
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("❌ OpenCV/PIL が必要です")
    print("   pip install opencv-python pillow")
    sys.exit(1)

from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter
from verantyx_cli.vision.experience_memory import ExperienceMemory
from verantyx_cli.vision.emotion_inference import EmotionInference, EmotionVisualizer


class ExperienceRecorder:
    """経験記録システム（自律的）"""

    def __init__(self, memory_path: Optional[Path] = None):
        """
        Initialize experience recorder

        Args:
            memory_path: 記憶ファイルのパス
        """
        print()
        print("=" * 70)
        print("🧠 Verantyx Vision - Experience Recorder")
        print("   自律的感情推測システム")
        print("=" * 70)
        print()

        # Cross変換エンジン（標準品質）
        print("⚙️  Cross変換エンジンを初期化中...")
        self.converter = MultiLayerCrossConverter(quality="standard")

        # 経験記憶
        print("📚 経験記憶を初期化中...")
        self.memory = ExperienceMemory(memory_path=memory_path)

        # 感情推測エンジン
        print("💭 感情推測エンジンを初期化中...")
        self.inference = EmotionInference(self.memory)

        # 感情可視化
        self.visualizer = EmotionVisualizer()

        # カメラ
        self.camera = None
        self.frame_count = 0

        # 現在の感情
        self.current_emotion = None

        # 観測頻度（フレーム数）
        self.observe_interval = 60  # 2秒に1回（30fps想定）

        # 予測検証用の前回Cross構造
        self.prev_cross = None

        print()
        print("✅ 初期化完了")
        print()

    def start(self):
        """経験記録セッションを開始"""
        if not CV2_AVAILABLE:
            print("❌ OpenCVが必要です")
            return 1

        # カメラを開く
        print("📷 カメラを起動中...")
        self.camera = cv2.VideoCapture(0)

        if not self.camera.isOpened():
            print("❌ カメラを開けませんでした")
            return 1

        # 解像度設定
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print()
        print("=" * 70)
        print("経験記録セッション開始")
        print("=" * 70)
        print()
        print("システムの動作:")
        print("  - カメラで観測した内容を自動的に記憶")
        print("  - 過去の経験と照合して感情を推測")
        print("  - 次の瞬間を予測して検証")
        print("  - ラベルなし・完全自律")
        print()
        print("操作:")
        print("  [Q] - 終了")
        print("  [S] - サマリー表示")
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
            ret, frame = self.camera.read()
            if not ret:
                print("❌ カメラからフレームを取得できませんでした")
                break

            self.frame_count += 1

            # 定期的に観測・推測
            if self.frame_count % self.observe_interval == 0:
                self._observe_and_infer(frame)

            # 感情を描画
            if self.current_emotion:
                self.visualizer.visualize(frame, self.current_emotion, self.inference)

            # ステータス表示
            self._draw_status(frame)

            # 画面表示
            cv2.imshow("Experience Recorder", frame)

            # キー入力
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == ord('Q'):
                print("\n👋 終了します")
                break
            elif key == ord('s') or key == ord('S'):
                self._print_summary()

    def _observe_and_infer(self, frame):
        """観測して推測"""
        print()
        print(f"👁️  観測 #{len(self.memory.timeline) + 1}")
        print("-" * 70)

        # 1. Cross構造に変換
        print("🔄 Cross構造に変換中...")
        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cross_structure = self.converter.convert(pil_image)

        # 2. 前回の予測を検証（2回目以降）
        if self.prev_cross and self.current_emotion:
            print("🎯 前回の予測を検証中...")
            reward = self.inference.validate_prediction(cross_structure)

        # 3. 経験を記録
        print("📝 経験を記録中...")
        self.memory.observe(cross_structure)

        # 4. 感情を推測
        print("💭 感情を推測中...")
        emotion = self.inference.infer(cross_structure)
        self.current_emotion = emotion

        # 5. 感情を言語化
        emotion_text = self.inference.express_emotion(emotion)
        print(f"   → {emotion_text}")

        # 6. 次回の検証用に保存
        self.prev_cross = cross_structure

        print("-" * 70)
        print()

    def _draw_status(self, frame):
        """ステータスを描画"""
        height, width = frame.shape[:2]

        # ステータスバー（下部）
        status_height = 40
        cv2.rectangle(
            frame,
            (0, height - status_height),
            (width, height),
            (0, 0, 0),
            -1
        )

        # ステータステキスト
        status_text = f"経験: {len(self.memory.timeline)} | パターン: {len(self.memory.patterns)} | フレーム: {self.frame_count}"

        cv2.putText(
            frame,
            status_text,
            (10, height - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1
        )

        # 次の観測まで
        next_observe = self.observe_interval - (self.frame_count % self.observe_interval)
        if next_observe < self.observe_interval:
            cv2.putText(
                frame,
                f"次の観測: {next_observe}f",
                (width - 150, height - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (100, 200, 100),
                1
            )

    def _print_summary(self):
        """サマリーを表示"""
        print()
        self.memory.print_summary()

        # 感情のサマリー
        emotion_summary = self.inference.get_emotion_summary()
        print("=" * 60)
        print("感情サマリー")
        print("=" * 60)
        print(f"感情履歴: {emotion_summary.get('total', 0)} 回")
        print()

        if emotion_summary.get('type_counts'):
            print("感情タイプの内訳:")
            for emotion_type, count in emotion_summary['type_counts'].items():
                print(f"  - {emotion_type}: {count} 回")
            print()

        avg_conf = emotion_summary.get('avg_confidence', 0)
        print(f"平均確信度: {avg_conf:.1%}")
        print()

        if emotion_summary.get('latest'):
            latest = emotion_summary['latest']
            emotion_text = self.inference.express_emotion(latest)
            print(f"現在の感情: {emotion_text}")

        print("=" * 60)
        print()

    def _cleanup(self):
        """クリーンアップ"""
        print()
        print("💾 経験を保存中...")
        self.memory.save()

        if self.camera:
            self.camera.release()

        cv2.destroyAllWindows()

        print()
        print("=" * 70)
        print("経験記録セッション終了")
        print("=" * 70)
        print()

        # 最終サマリー
        self._print_summary()


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Experience Recorder - 自律的感情推測システム"
    )

    parser.add_argument(
        "--memory-path",
        type=str,
        help="記憶ファイルのパス（デフォルト: ~/.verantyx/experience_memory.json）"
    )

    parser.add_argument(
        "--observe-interval",
        type=int,
        default=60,
        help="観測間隔（フレーム数、デフォルト: 60）"
    )

    args = parser.parse_args()

    # 記憶パス
    memory_path = None
    if args.memory_path:
        memory_path = Path(args.memory_path).expanduser().absolute()

    # レコーダー起動
    recorder = ExperienceRecorder(memory_path=memory_path)

    if args.observe_interval:
        recorder.observe_interval = args.observe_interval

    return recorder.start()


if __name__ == "__main__":
    sys.exit(main())
