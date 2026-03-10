#!/usr/bin/env python3
"""
軽量版継続的実行デーモン
30fps達成のための最適化版

最適化内容:
- 画像サイズを32x32に縮小
- ログ出力を削減
- 同期処理を簡略化
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import numpy as np
from PIL import Image

# Import production components
from image_to_cross import ImageToCrossConverter
from emotion_dna_system_with_learning import EmotionDNASystemWithLearning
from global_cross_registry import GlobalCrossRegistry, get_global_registry


class LightweightContinuousDaemon:
    """
    軽量版継続的実行デーモン
    30fps達成を目標とした最適化版
    """

    def __init__(self, use_gpu: bool = False):
        """Initialize"""
        # 画像変換器（軽量: 32x32）
        self.image_converter = ImageToCrossConverter(
            use_gpu=use_gpu,
            target_size=(32, 32)
        )

        # 学習統合感情DNAシステム
        emotion_jcross_file = Path(__file__).parent.parent / "vision" / "emotion_dna_cross.jcross"
        self.emotion_system = EmotionDNASystemWithLearning(jcross_file=str(emotion_jcross_file))

        # グローバルレジストリ
        self.registry = get_global_registry()
        self._register_emotion_crosses()

        # 学習状態
        self.frame_count = 0
        self.learning_history: List[Dict[str, Any]] = []

        # Cross記憶バンク（軽量: 最大20）
        self.cross_memory_bank = []
        self.max_memory_size = 20

        print("✅ 軽量版デーモン初期化完了")
        print()

    def _register_emotion_crosses(self):
        """感情DNAのCross構造を登録"""
        multi_cross = self.emotion_system.multi_cross
        for name in self.emotion_system.emotion_crosses.keys():
            cross_name = f"{name}Cross"
            if cross_name in multi_cross.crosses:
                self.registry.register(cross_name, multi_cross.crosses[cross_name], group="emotion")

    def process_frame_lightweight(self, image: Image.Image) -> Dict[str, Any]:
        """
        軽量版フレーム処理

        Args:
            image: PIL Image

        Returns:
            処理結果
        """
        start_time = time.time()

        # 画像→Cross変換
        image_cross = self.image_converter.convert(image)

        # Cross記憶バンク
        self.cross_memory_bank.append(image_cross)
        if len(self.cross_memory_bank) > self.max_memory_size:
            self.cross_memory_bank.pop(0)

        # 同調度計算（簡略版: 最新5個のみ）
        sync_scores = []
        if len(self.cross_memory_bank) > 1:
            for past_cross in self.cross_memory_bank[-5:]:
                if past_cross != image_cross:
                    sync = image_cross.sync_with(past_cross, layer=4)
                    sync_scores.append(sync)

        avg_sync = np.mean(sync_scores) if sync_scores else 0.0

        # 生理・認知状態
        physiological_state = {
            "体温": 37.0,
            "血圧": 120.0 + (1.0 - avg_sync) * 30.0,
            "心拍数": 70.0 + (1.0 - avg_sync) * 50.0,
            "血糖値": 100.0,
            "痛み": 0.0,
            "エネルギー": 0.8
        }

        cognitive_state = {
            "新規性": 1.0 - avg_sync,
            "予測成功": avg_sync,
            "予測失敗": 1.0 - avg_sync,
            "学習成功": avg_sync * 0.8,
            "理解": avg_sync * 0.7
        }

        # 感情判定
        self.emotion_system.determine_emotion(physiological_state, cognitive_state)

        emotion_name = self.emotion_system.current_emotion_name
        emotion_intensity = self.emotion_system.current_emotion_intensity

        # 感情発火時のみグローバル同調（ログなし）
        if emotion_name != "なし":
            allocation = self.emotion_system.get_resource_allocation()
            sync_mode = self.emotion_system.get_sync_mode()
            # ログ出力を抑制してパフォーマンス向上
            self.registry.emotion_interrupt(emotion_name, allocation, sync_mode)

        elapsed = time.time() - start_time

        # 軽量版結果
        result = {
            "frame": self.frame_count,
            "sync": float(avg_sync),
            "emotion": emotion_name,
            "intensity": emotion_intensity,
            "time_ms": elapsed * 1000
        }

        self.learning_history.append(result)
        self.frame_count += 1

        return result

    def run_continuous(self, target_fps: int = 30, duration_seconds: Optional[int] = None):
        """
        継続的実行

        Args:
            target_fps: 目標FPS
            duration_seconds: 実行時間（秒）
        """
        target_frame_time = 1.0 / target_fps

        print("=" * 80)
        print(f"軽量版継続的実行 (目標: {target_fps}fps)")
        print("=" * 80)
        print()
        print("Ctrl+C で停止")
        print()

        start_time = time.time()
        frame_times = []

        try:
            while True:
                frame_start = time.time()

                # ランダム画像（軽量: 32x32）
                random_image = Image.fromarray(
                    (np.random.rand(32, 32, 3) * 255).astype(np.uint8)
                )

                # 処理
                result = self.process_frame_lightweight(random_image)

                frame_elapsed = time.time() - frame_start
                frame_times.append(frame_elapsed)

                # 1秒ごとに統計表示
                if self.frame_count % target_fps == 0:
                    elapsed = time.time() - start_time
                    actual_fps = self.frame_count / elapsed
                    avg_frame_time = np.mean(frame_times[-target_fps:])

                    print(f"[{int(elapsed)}s] "
                          f"Frame {self.frame_count}, "
                          f"実FPS: {actual_fps:.1f}, "
                          f"処理時間: {avg_frame_time*1000:.1f}ms, "
                          f"感情: {result['emotion']}({result['intensity']:.2f})")

                # 目標FPSに合わせて待機
                sleep_time = target_frame_time - frame_elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

                # 実行時間制限
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    break

        except KeyboardInterrupt:
            print()
            print("停止シグナルを受信")

        # 最終統計
        total_elapsed = time.time() - start_time
        actual_fps = self.frame_count / total_elapsed
        avg_frame_time = np.mean(frame_times)

        print()
        print("=" * 80)
        print("実行結果")
        print("=" * 80)
        print()
        print(f"総実行時間: {total_elapsed:.1f}秒")
        print(f"総フレーム数: {self.frame_count}")
        print(f"目標FPS: {target_fps}")
        print(f"実際のFPS: {actual_fps:.2f}")
        print(f"平均処理時間: {avg_frame_time*1000:.1f}ms/frame")
        print()

        # 学習効果
        if len(self.learning_history) >= 10:
            initial = np.mean([h["intensity"] for h in self.learning_history[:5]])
            final = np.mean([h["intensity"] for h in self.learning_history[-5:]])
            print(f"初期強度: {initial:.3f}")
            print(f"最終強度: {final:.3f}")
            print(f"向上: {'+' if final > initial else ''}{final - initial:.3f}")
            print()

        # 学習履歴保存
        log_dir = Path.home() / ".verantyx" / "production_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        history_file = log_dir / f"lightweight_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(self.learning_history, f, ensure_ascii=False, indent=2)

        print(f"学習履歴を保存: {history_file}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='軽量版継続的実行デーモン')
    parser.add_argument('--fps', type=int, default=30, help='目標FPS（デフォルト: 30）')
    parser.add_argument('--duration', type=int, default=None, help='実行時間（秒）')
    parser.add_argument('--gpu', action='store_true', help='GPUを使用')

    args = parser.parse_args()

    print("=" * 80)
    print("軽量版JCross学習デーモン")
    print("=" * 80)
    print()
    print(f"目標FPS: {args.fps}")
    print(f"実行時間: {'無限（Ctrl+Cで停止）' if args.duration is None else f'{args.duration}秒'}")
    print(f"画像サイズ: 32x32（最適化）")
    print()

    daemon = LightweightContinuousDaemon(use_gpu=args.gpu)

    daemon.run_continuous(
        target_fps=args.fps,
        duration_seconds=args.duration
    )

    print()
    print("=" * 80)
    print("実行完了")
    print("=" * 80)


if __name__ == "__main__":
    main()
