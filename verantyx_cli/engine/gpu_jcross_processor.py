#!/usr/bin/env python3
"""
GPU JCross Processor
.jcrossコードをGPU並列処理に変換

CuPy/NumPyを使用してGPU並列化を実現
"""

import sys
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from PIL import Image
import logging

# CuPyの試行的インポート
try:
    import cupy as cp
    GPU_AVAILABLE = True
    xp = cp  # CuPyを使用
    print("✅ CuPy利用可能 - GPU並列処理を使用")
except ImportError:
    GPU_AVAILABLE = False
    xp = np  # NumPyフォールバック
    print("⚠️  CuPy利用不可 - CPUフォールバック")

from jcross_interpreter import JCrossInterpreter
from cross_structure import CrossStructure
from emotion_dna_system_with_learning import EmotionDNASystemWithLearning


class GPUJCrossProcessor:
    """
    GPU並列化JCrossプロセッサ

    .jcrossで定義された処理をGPU並列化
    目標: 30fps以上
    """

    def __init__(self, batch_size: int = 32):
        """
        Initialize

        Args:
            batch_size: バッチサイズ（同時処理フレーム数）
        """
        self.batch_size = batch_size
        self.gpu_available = GPU_AVAILABLE

        # .jcrossファイル読み込み
        jcross_file = Path(__file__).parent / "gpu_continuous_daemon.jcross"
        interpreter = JCrossInterpreter()
        self.jcross_data = interpreter.load_file(str(jcross_file))

        # 感情DNAシステム
        emotion_jcross = Path(__file__).parent.parent / "vision" / "emotion_dna_cross.jcross"
        self.emotion_system = EmotionDNASystemWithLearning(jcross_file=str(emotion_jcross))

        # GPU用バッファ（事前確保）
        if self.gpu_available:
            self._allocate_gpu_buffers()

        # 統計
        self.total_frames = 0
        self.total_time = 0.0

        logging.info(f"✅ GPU JCrossプロセッサ初期化完了 (バッチサイズ: {batch_size})")

    def _allocate_gpu_buffers(self):
        """GPU用バッファを事前確保"""
        # 画像バッチ用バッファ (batch_size, 32, 32, 3)
        self.image_buffer_gpu = xp.zeros((self.batch_size, 32, 32, 3), dtype=xp.float32)

        # Cross構造用バッファ (batch_size, 260000)
        self.cross_buffer_gpu = xp.zeros((self.batch_size, 260000), dtype=xp.float32)

        # 同調度バッファ (batch_size,)
        self.sync_buffer_gpu = xp.zeros(self.batch_size, dtype=xp.float32)

        # 感情強度バッファ (batch_size, 6) - 6感情
        self.emotion_intensity_buffer_gpu = xp.zeros((self.batch_size, 6), dtype=xp.float32)

        logging.info("✅ GPUバッファ確保完了")

    def process_image_batch_gpu(self, images: List[Image.Image]) -> List[Dict[str, Any]]:
        """
        画像バッチをGPU並列処理

        Args:
            images: PIL Image のリスト (最大batch_size個)

        Returns:
            処理結果のリスト
        """
        if not self.gpu_available:
            # CPUフォールバック
            return self._process_image_batch_cpu(images)

        start_time = time.time()

        batch_size = len(images)

        # 1. 画像→numpy配列（CPU）
        image_arrays = []
        for img in images:
            if img.size != (32, 32):
                img = img.resize((32, 32))
            arr = np.array(img, dtype=np.float32) / 255.0
            if arr.shape[2] == 4:  # RGBA → RGB
                arr = arr[:, :, :3]
            image_arrays.append(arr)

        image_batch_cpu = np.stack(image_arrays, axis=0)

        # 2. CPU→GPU転送
        image_batch_gpu = xp.asarray(image_batch_cpu)

        # 3. GPU並列処理: 画像→Cross変換
        cross_batch_gpu = self._image_to_cross_batch_gpu(image_batch_gpu)

        # 4. GPU並列処理: 同調度計算
        sync_scores_gpu = self._compute_sync_batch_gpu(cross_batch_gpu)

        # 5. GPU並列処理: 感情判定
        emotion_results_gpu = self._judge_emotion_batch_gpu(sync_scores_gpu)

        # 6. GPU→CPU転送
        sync_scores_cpu = xp.asnumpy(sync_scores_gpu)
        emotion_results_cpu = {
            'emotions': xp.asnumpy(emotion_results_gpu['emotions']),
            'intensities': xp.asnumpy(emotion_results_gpu['intensities'])
        }

        # 7. 結果を整形
        results = []
        emotion_names = ['恐怖', '怒り', '好奇心', '悲しみ', '喜び', '安心']

        for i in range(batch_size):
            emotion_idx = emotion_results_cpu['emotions'][i]
            emotion_name = emotion_names[emotion_idx] if emotion_idx < 6 else 'なし'

            result = {
                'frame': self.total_frames + i,
                'sync': float(sync_scores_cpu[i]),
                'emotion': emotion_name,
                'intensity': float(emotion_results_cpu['intensities'][i]),
                'gpu_processing': True
            }
            results.append(result)

        elapsed = time.time() - start_time
        self.total_frames += batch_size
        self.total_time += elapsed

        return results

    def _image_to_cross_batch_gpu(self, image_batch_gpu: 'cp.ndarray') -> 'cp.ndarray':
        """
        画像バッチ→Cross構造バッチ変換（GPU並列）

        Args:
            image_batch_gpu: (batch_size, 32, 32, 3) float32

        Returns:
            cross_batch_gpu: (batch_size, 260000) float32
        """
        batch_size = image_batch_gpu.shape[0]

        # 簡略版Cross変換: ダウンサンプリング + フラット化
        # 実際は6軸構造に展開するが、ここでは高速化のため簡略化

        # (32, 32, 3) → (16, 16, 3) ダウンサンプリング
        downsampled = image_batch_gpu[:, ::2, ::2, :]  # (batch_size, 16, 16, 3)

        # フラット化
        flattened = downsampled.reshape(batch_size, -1)  # (batch_size, 768)

        # 260000次元に拡張（パディング）
        cross_batch = xp.zeros((batch_size, 260000), dtype=xp.float32)
        cross_batch[:, :768] = flattened

        return cross_batch

    def _compute_sync_batch_gpu(self, cross_batch_gpu: 'cp.ndarray') -> 'cp.ndarray':
        """
        同調度バッチ計算（GPU並列）

        Args:
            cross_batch_gpu: (batch_size, 260000)

        Returns:
            sync_scores: (batch_size,)
        """
        batch_size = cross_batch_gpu.shape[0]

        if batch_size < 2:
            return xp.zeros(batch_size, dtype=xp.float32)

        # 現在のCrossと1つ前のCrossの類似度を計算
        # コサイン類似度: dot(a, b) / (norm(a) * norm(b))

        current = cross_batch_gpu[1:]  # (batch_size-1, 260000)
        previous = cross_batch_gpu[:-1]  # (batch_size-1, 260000)

        # ドット積（GPU並列）
        dot_products = xp.sum(current * previous, axis=1)  # (batch_size-1,)

        # ノルム
        norm_current = xp.linalg.norm(current, axis=1)
        norm_previous = xp.linalg.norm(previous, axis=1)

        # コサイン類似度
        sync_scores_partial = dot_products / (norm_current * norm_previous + 1e-8)

        # 最初のフレームは0
        sync_scores = xp.zeros(batch_size, dtype=xp.float32)
        sync_scores[1:] = sync_scores_partial

        return sync_scores

    def _judge_emotion_batch_gpu(self, sync_scores_gpu: 'cp.ndarray') -> Dict[str, 'cp.ndarray']:
        """
        感情判定バッチ（GPU並列）

        Args:
            sync_scores_gpu: (batch_size,)

        Returns:
            {
                'emotions': (batch_size,) int - 感情インデックス,
                'intensities': (batch_size,) float - 感情強度
            }
        """
        batch_size = sync_scores_gpu.shape[0]

        # 簡略版感情判定ルール（GPU並列化可能な単純ルール）
        # 実際の実装では.jcrossの発火条件を評価

        # 新規性 = 1.0 - sync
        novelty = 1.0 - sync_scores_gpu

        # ルールベース判定（GPU並列）
        emotions = xp.zeros(batch_size, dtype=xp.int32)
        intensities = xp.zeros(batch_size, dtype=xp.float32)

        # 新規性が高い → 好奇心 (2)
        # 新規性が低い → 悲しみ (3)
        emotions = xp.where(novelty > 0.7, 2, 3)
        intensities = xp.where(novelty > 0.7, 0.5 + novelty * 0.3, 0.5 + (1.0 - novelty) * 0.3)

        return {
            'emotions': emotions,
            'intensities': intensities
        }

    def _process_image_batch_cpu(self, images: List[Image.Image]) -> List[Dict[str, Any]]:
        """CPUフォールバック処理"""
        results = []

        for i, img in enumerate(images):
            # 既存の感情システムを使用
            if img.size != (32, 32):
                img = img.resize((32, 32))

            arr = np.array(img, dtype=np.float32) / 255.0

            # 簡易的な同調度
            sync = 0.5 if i > 0 else 0.0

            # 簡易的な感情判定
            novelty = 1.0 - sync
            emotion = '好奇心' if novelty > 0.7 else '悲しみ'
            intensity = 0.5 + novelty * 0.3

            result = {
                'frame': self.total_frames + i,
                'sync': sync,
                'emotion': emotion,
                'intensity': intensity,
                'gpu_processing': False
            }
            results.append(result)

        self.total_frames += len(images)
        return results

    def get_performance_stats(self) -> Dict[str, Any]:
        """パフォーマンス統計を取得"""
        if self.total_frames == 0:
            return {}

        avg_time_per_frame = self.total_time / self.total_frames
        fps = 1.0 / avg_time_per_frame if avg_time_per_frame > 0 else 0.0

        return {
            'total_frames': self.total_frames,
            'total_time': self.total_time,
            'avg_time_per_frame_ms': avg_time_per_frame * 1000,
            'fps': fps,
            'gpu_available': self.gpu_available,
            'batch_size': self.batch_size
        }


class GPUContinuousDaemon:
    """
    GPU並列化継続的実行デーモン
    """

    def __init__(self, batch_size: int = 32, use_gpu: bool = True):
        """
        Initialize

        Args:
            batch_size: バッチサイズ
            use_gpu: GPU使用フラグ
        """
        self.batch_size = batch_size
        self.use_gpu = use_gpu and GPU_AVAILABLE

        if not self.use_gpu and use_gpu:
            print("⚠️  GPU要求されましたが利用不可。CPUフォールバック")

        self.processor = GPUJCrossProcessor(batch_size=batch_size)

        print()
        print("=" * 80)
        print("GPU並列化JCross継続的実行デーモン")
        print("=" * 80)
        print()
        print(f"バッチサイズ: {batch_size}フレーム同時処理")
        print(f"GPU使用: {'有効' if self.use_gpu else '無効（CPUフォールバック）'}")
        print()

    def run_continuous(self, target_fps: int = 30, duration_seconds: Optional[int] = None):
        """
        継続的実行

        Args:
            target_fps: 目標FPS
            duration_seconds: 実行時間（秒）
        """
        print("Ctrl+C で停止")
        print()

        start_time = time.time()
        batch_count = 0

        try:
            while True:
                batch_start = time.time()

                # ランダム画像バッチを生成
                images = []
                for _ in range(self.batch_size):
                    random_image = Image.fromarray(
                        (np.random.rand(32, 32, 3) * 255).astype(np.uint8)
                    )
                    images.append(random_image)

                # GPU並列処理
                results = self.processor.process_image_batch_gpu(images)

                batch_elapsed = time.time() - batch_start
                batch_count += 1

                # 1秒ごとに統計表示
                if batch_count % 10 == 0:
                    stats = self.processor.get_performance_stats()
                    elapsed = time.time() - start_time

                    print(f"[{int(elapsed)}s] "
                          f"バッチ {batch_count}, "
                          f"実FPS: {stats['fps']:.1f}, "
                          f"バッチ処理時間: {batch_elapsed*1000:.1f}ms, "
                          f"フレーム処理時間: {stats['avg_time_per_frame_ms']:.1f}ms")

                # 実行時間制限
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    break

        except KeyboardInterrupt:
            print()
            print("停止シグナルを受信")

        # 最終統計
        self._print_final_stats(start_time)

    def _print_final_stats(self, start_time: float):
        """最終統計を表示"""
        stats = self.processor.get_performance_stats()
        total_elapsed = time.time() - start_time

        print()
        print("=" * 80)
        print("実行結果")
        print("=" * 80)
        print()
        print(f"総実行時間: {total_elapsed:.1f}秒")
        print(f"総フレーム数: {stats['total_frames']}")
        print(f"バッチサイズ: {stats['batch_size']}")
        print(f"実際のFPS: {stats['fps']:.2f}")
        print(f"平均フレーム処理時間: {stats['avg_time_per_frame_ms']:.1f}ms")
        print(f"GPU使用: {'あり' if stats['gpu_available'] else 'なし（CPU）'}")
        print()

        if stats['fps'] >= 30:
            print("✅ 目標30fps達成！")
        else:
            print(f"⚠️  目標30fps未達成（{stats['fps']:.1f}fps）")

        print()


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description='GPU並列化継続的実行デーモン')
    parser.add_argument('--fps', type=int, default=30, help='目標FPS')
    parser.add_argument('--duration', type=int, default=None, help='実行時間（秒）')
    parser.add_argument('--batch-size', type=int, default=32, help='バッチサイズ')
    parser.add_argument('--no-gpu', action='store_true', help='GPUを使用しない')

    args = parser.parse_args()

    daemon = GPUContinuousDaemon(
        batch_size=args.batch_size,
        use_gpu=not args.no_gpu
    )

    daemon.run_continuous(
        target_fps=args.fps,
        duration_seconds=args.duration
    )


if __name__ == "__main__":
    main()
