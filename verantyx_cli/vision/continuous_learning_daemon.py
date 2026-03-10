#!/usr/bin/env python3
"""
Continuous Learning Daemon
継続的学習デーモン

バックグラウンドでSSD内のデータから継続的に学習。
Neural Engineネイティブで低電力・高効率。
"""

import sys
import os
import signal
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import cv2
import numpy as np
from PIL import Image
import threading
import queue

from verantyx_cli.engine.jcross_bootstrap import ZeroYearOldJCross
from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter
from verantyx_cli.engine.neural_engine_backend import neural_engine, power_optimizer
from verantyx_cli.vision.developmental_processors import DevelopmentalStageSystem


class ContinuousLearningDaemon:
    """
    継続的学習デーモン

    SSD内の動画を見つけて、バックグラウンドで学習し続ける。
    """

    def __init__(self, log_dir: Path = None):
        """
        Initialize daemon

        Args:
            log_dir: ログディレクトリ
        """
        self.running = False
        self.paused = False

        # ログディレクトリ
        if log_dir is None:
            log_dir = Path.home() / ".verantyx" / "learning_logs"
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 学習システム
        self.baby = None
        self.converter = None
        self.developmental_system = None

        # 学習キュー
        self.video_queue = queue.Queue()
        self.processed_videos = set()

        # 統計
        self.stats = {
            "start_time": None,
            "total_videos": 0,
            "total_frames": 0,
            "total_predictions": 0,
            "successful_predictions": 0,
            "discovered_patterns": 0,
            "learning_events": 0,
            "uptime_seconds": 0
        }

        # スレッド
        self.learning_thread = None
        self.monitor_thread = None

        print("🤖 継続的学習デーモン初期化完了")

    def initialize_systems(self):
        """システムを初期化"""
        print()
        print("=" * 80)
        print("🧠 学習システム初期化")
        print("=" * 80)
        print()

        # JCrossシステム
        print("JCrossシステム起動中...")
        self.baby = ZeroYearOldJCross()
        print("✅ JCross起動完了")
        print()

        # Cross変換器（高速モード）
        print("Cross変換器初期化中...")
        self.converter = MultiLayerCrossConverter(quality="fast")
        print("✅ Cross変換器起動完了")
        print()

        # 発達段階システム（1000倍速成長）
        print("発達段階システム初期化中...")
        self.developmental_system = DevelopmentalStageSystem(growth_speed=1000.0)
        print("✅ 発達段階システム起動完了")
        print()

        # Neural Engine最適化
        print("Neural Engine最適化...")
        neural_stats = neural_engine.get_stats()
        print(f"  Neural Engine: {'✅ 有効' if neural_stats['neural_engine_enabled'] else '❌ 無効'}")
        print()

        # 電力モード設定
        power_optimizer.set_power_mode("balanced")
        print()

    def scan_ssd_for_videos(self, search_paths: List[Path] = None) -> List[Path]:
        """
        SSD内の動画をスキャン

        Args:
            search_paths: 検索パス

        Returns:
            動画ファイルのリスト
        """
        if search_paths is None:
            search_paths = [
                Path.home() / "Desktop",
                Path.home() / "Downloads",
                Path.home() / "Movies",
                Path.home() / "Documents",
                Path("/Volumes/PREDATOR GM7000 4TB"),  # 外付けSSD
            ]

        print("📹 SSD内の動画をスキャン中...")
        print()

        videos = []
        extensions = ['.mp4', '.mov', '.avi', '.mkv']

        for search_path in search_paths:
            if not search_path.exists():
                continue

            print(f"  スキャン: {search_path}")
            for ext in extensions:
                found = list(search_path.glob(f'*{ext}'))
                videos.extend(found)

        # 重複を除去
        videos = list(set(videos))
        print()
        print(f"✅ {len(videos)}個の動画を発見")
        print()

        return videos

    def add_videos_to_queue(self, videos: List[Path]):
        """動画を学習キューに追加"""
        for video in videos:
            if str(video) not in self.processed_videos:
                self.video_queue.put(video)
                print(f"  📥 キュー追加: {video.name}")

    def process_video(self, video_path: Path, max_frames: int = 100):
        """
        動画を処理

        Args:
            video_path: 動画パス
            max_frames: 最大フレーム数
        """
        if self.paused:
            return

        print()
        print("-" * 80)
        print(f"🎬 処理開始: {video_path.name}")
        print("-" * 80)
        print()

        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                print(f"❌ 動画を開けませんでした: {video_path.name}")
                return

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            print(f"動画情報:")
            print(f"  総フレーム: {total_frames}")
            print(f"  FPS: {fps:.2f}")
            print()

            # スキップ間隔を動的に決定
            skip_interval = max(1, total_frames // max_frames)

            frame_count = 0
            processed_count = 0
            frame_history = []

            while self.running and not self.paused:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                # スキップ
                if (frame_count - 1) % skip_interval != 0:
                    continue

                # 最大フレーム数
                if processed_count >= max_frames:
                    break

                # フレーム処理
                self._process_frame(frame, frame_count, frame_history)
                processed_count += 1
                self.stats["total_frames"] += 1

                # 低電力最適化
                if power_optimizer.should_sleep(processed_count):
                    power_optimizer.sleep()

                # 進捗（10フレームごと）
                if processed_count % 10 == 0:
                    progress = (processed_count / max_frames) * 100
                    print(f"  進捗: {processed_count}/{max_frames} ({progress:.1f}%)")

            cap.release()

            # 統計更新
            self.stats["total_videos"] += 1
            self.processed_videos.add(str(video_path))

            print()
            print(f"✅ 完了: {video_path.name} ({processed_count}フレーム処理)")
            print()

            # ログ保存
            self._save_log(video_path, processed_count)

        except Exception as e:
            print(f"❌ エラー: {e}")
            import traceback
            traceback.print_exc()

    def _process_frame(
        self,
        frame_bgr: np.ndarray,
        frame_number: int,
        frame_history: list
    ):
        """フレームを処理"""
        # BGR → RGB
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # リサイズ
        frame_resized = cv2.resize(frame_rgb, (64, 64))

        # PIL Image
        frame_pil = Image.fromarray(frame_resized)

        # Cross構造変換（Neural Engine加速）
        cross_structure = self.converter.convert(frame_pil)

        # 履歴に追加
        frame_history.append({
            "frame": frame_number,
            "cross": cross_structure,
            "points": cross_structure['metadata']['total_points']
        })

        if len(frame_history) > 10:
            frame_history.pop(0)

        # 予測（3フレーム以上）
        if len(frame_history) >= 3:
            self._predict_and_learn(frame_history)

        # 経験として保存（発達段階に応じてアップグレード）
        discomfort_info = self.baby._calc_total_discomfort()

        # 基本経験データ
        experience = {
            "cross_structure": cross_structure,
            "discomfort": discomfort_info["総不快感"],
            "context": {
                "type": "continuous_learning",
                "frame": frame_number,
                "timestamp": datetime.now().isoformat()
            }
        }

        # 発達段階に応じて記憶をアップグレード
        upgraded_experience = self.developmental_system.upgrade_memory(experience)

        # 年齢を更新（フレーム処理ごとに0.1秒経過と仮定）
        new_stage = self.developmental_system.update_age(0.1)

        # 保存
        self.baby._store_experience(
            cross_structure=cross_structure,
            discomfort=upgraded_experience["discomfort"],
            context=upgraded_experience["context"]
        )

    def _predict_and_learn(self, frame_history: list):
        """予測して学習"""
        prev_prev = frame_history[-3]
        prev = frame_history[-2]
        current = frame_history[-1]

        # 予測（点数ベース）
        prev_diff = prev['points'] - prev_prev['points']
        predicted_points = prev['points'] + prev_diff
        actual_points = current['points']

        error = abs(predicted_points - actual_points) / max(1, actual_points)

        # 統計更新
        self.stats["total_predictions"] += 1

        if error < 0.05:
            # 成功
            self.stats["successful_predictions"] += 1
        else:
            # 失敗 → 学習イベント
            if error > 0.2:
                self.stats["discovered_patterns"] += 1
                self.stats["learning_events"] += 1

    def learning_loop(self):
        """学習ループ（スレッドで実行）"""
        print()
        print("🔄 学習ループ開始")
        print()

        while self.running:
            try:
                # キューから動画を取得（タイムアウト付き）
                video_path = self.video_queue.get(timeout=1.0)

                # 動画を処理
                self.process_video(video_path, max_frames=100)

                self.video_queue.task_done()

            except queue.Empty:
                # キューが空
                if not self.paused:
                    # 新しい動画をスキャン
                    videos = self.scan_ssd_for_videos()
                    new_videos = [v for v in videos if str(v) not in self.processed_videos]

                    if new_videos:
                        print(f"🆕 新しい動画を発見: {len(new_videos)}個")
                        self.add_videos_to_queue(new_videos)
                    else:
                        # 新しい動画がない → スリープ
                        time.sleep(60)  # 1分待つ

            except Exception as e:
                print(f"❌ 学習ループエラー: {e}")
                time.sleep(5)

    def monitor_loop(self):
        """モニターループ（統計表示）"""
        while self.running:
            time.sleep(300)  # 5分ごと

            if not self.paused:
                self._print_stats()

    def _print_stats(self):
        """統計を表示"""
        uptime = time.time() - self.stats["start_time"]
        self.stats["uptime_seconds"] = uptime

        print()
        print("=" * 80)
        print("📊 学習統計（継続的学習デーモン）")
        print("=" * 80)
        print()
        print(f"稼働時間: {uptime/3600:.1f}時間")
        print(f"処理済み動画: {self.stats['total_videos']}")
        print(f"処理済みフレーム: {self.stats['total_frames']}")
        print()

        if self.stats["total_predictions"] > 0:
            success_rate = (self.stats["successful_predictions"] /
                           self.stats["total_predictions"]) * 100
            print(f"予測:")
            print(f"  総回数: {self.stats['total_predictions']}")
            print(f"  成功: {self.stats['successful_predictions']}")
            print(f"  成功率: {success_rate:.1f}%")
            print()

        print(f"発見パターン: {self.stats['discovered_patterns']}")
        print(f"学習イベント: {self.stats['learning_events']}")
        print()

        # システム状態
        status = self.baby.get_status()
        print(f"記憶:")
        print(f"  総経験数: {status['記憶']['総経験数']}")
        print(f"  クラスタ数: {status['記憶']['クラスタ数']}")
        print()

        # 発達段階
        dev_status = self.developmental_system.get_status()
        print(f"発達段階:")
        print(f"  年齢: {dev_status['年齢']:.2f}歳")
        print(f"  段階: {dev_status['段階']}")
        print(f"  記憶形式: {dev_status['記憶形式']}")
        print(f"  空間記憶: {'有効' if dev_status['空間記憶'] else '無効'}")
        print()
        print("=" * 80)
        print()

    def _save_log(self, video_path: Path, processed_frames: int):
        """ログを保存"""
        log_file = self.log_dir / f"learning_log_{datetime.now():%Y%m%d_%H%M%S}.json"

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "video": str(video_path),
            "processed_frames": processed_frames,
            "stats": self.stats,
            "memory": self.baby.get_status(),
            "developmental_stage": self.developmental_system.get_status()
        }

        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

    def start(self):
        """デーモン開始"""
        if self.running:
            print("⚠️  既に実行中です")
            return

        print()
        print("=" * 80)
        print("🚀 継続的学習デーモン起動")
        print("=" * 80)
        print()

        # システム初期化
        self.initialize_systems()

        # 初回スキャン
        videos = self.scan_ssd_for_videos()
        self.add_videos_to_queue(videos)

        # 統計開始
        self.stats["start_time"] = time.time()

        # 実行フラグ
        self.running = True

        # スレッド開始
        self.learning_thread = threading.Thread(target=self.learning_loop, daemon=True)
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)

        self.learning_thread.start()
        self.monitor_thread.start()

        print()
        print("✅ デーモン起動完了")
        print()
        print("コマンド:")
        print("  Ctrl+C: 停止")
        print("  プロセスID:", os.getpid())
        print()
        print("ログディレクトリ:", self.log_dir)
        print()
        print("=" * 80)
        print()

    def stop(self):
        """デーモン停止"""
        print()
        print("🛑 停止中...")
        print()

        self.running = False

        # スレッド終了を待つ
        if self.learning_thread:
            self.learning_thread.join(timeout=5)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        # 最終統計
        self._print_stats()

        print("✅ 停止完了")
        print()

    def pause(self):
        """一時停止"""
        self.paused = True
        print("⏸️  一時停止")

    def resume(self):
        """再開"""
        self.paused = False
        print("▶️  再開")


def signal_handler(signum, frame):
    """シグナルハンドラ"""
    print()
    print("シグナル受信:", signum)
    if daemon:
        daemon.stop()
    sys.exit(0)


daemon = None


def main():
    """メイン関数"""
    global daemon

    print()
    print("=" * 80)
    print("🤖 Verantyx 継続的学習デーモン")
    print("=" * 80)
    print()

    # シグナルハンドラ登録
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # デーモン作成
    daemon = ContinuousLearningDaemon()

    # 起動
    daemon.start()

    # メインループ（デーモンとして実行）
    try:
        while daemon.running:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
