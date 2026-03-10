#!/usr/bin/env python3
"""
JCross Learning Daemon
.jcrossフル実装学習デーモン

Phase 9: 新しい学習デーモン
- ImageToCrossConverterで動画フレーム→Cross構造変換
- EmotionDNASystemで感情ベース学習
- GlobalCrossRegistryで全ノード同調
- GPUCrossStructureで高速演算
- 古い「おもちゃデーモン」を置き換える本番実装
"""

import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import threading
import queue

import numpy as np
from PIL import Image

# Import all Phase 1-8 components
from image_to_cross import ImageToCrossConverter
from emotion_dna_system import EmotionDNASystem
from global_cross_registry import GlobalCrossRegistry, get_global_registry
from gpu_cross_structure import GPUCrossStructure
from large_cross_structure import LargeCrossStructure


class JCrossLearningDaemon:
    """
    .jcrossフル実装学習デーモン

    全Phase統合:
    - Phase 1-3: .jcross読み込みとCross構造実行
    - Phase 4: 全ノード同調
    - Phase 5: 制御構文
    - Phase 6: 260,000点大規模構造
    - Phase 7: GPU並列化
    - Phase 8: 実画像処理
    - Phase 9: 統合デーモン（本ファイル）
    """

    def __init__(
        self,
        emotion_jcross_file: Optional[str] = None,
        use_gpu: bool = False,
        log_dir: Optional[str] = None
    ):
        """
        Initialize

        Args:
            emotion_jcross_file: emotion_dna_cross.jcrossファイルパス
            use_gpu: GPUを使用するか
            log_dir: ログディレクトリ
        """
        # ログ設定
        self.log_dir = Path(log_dir) if log_dir else Path.home() / ".verantyx" / "learning_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        log_file = self.log_dir / f"jcross_daemon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

        self.logger = logging.getLogger(__name__)

        # Phase 8: 画像変換器
        self.logger.info("Phase 8: ImageToCrossConverterを初期化")
        self.image_converter = ImageToCrossConverter(
            use_gpu=use_gpu,
            target_size=(64, 64)
        )

        # Phase 3: 感情DNAシステム
        self.logger.info("Phase 3: EmotionDNASystemを初期化")
        if emotion_jcross_file is None:
            # デフォルトパス
            emotion_jcross_file = Path(__file__).parent.parent / "vision" / "emotion_dna_cross.jcross"

        self.emotion_system = EmotionDNASystem(jcross_file=str(emotion_jcross_file))

        # Phase 4: グローバルレジストリ
        self.logger.info("Phase 4: GlobalCrossRegistryを取得")
        self.registry = get_global_registry()

        # 感情DNAのCross構造を全て登録
        self._register_emotion_crosses()

        # 学習状態
        self.frame_count = 0
        self.learning_history: List[Dict[str, Any]] = []

        # Cross記憶バンク（過去のCross構造を保存）
        self.cross_memory_bank: List[LargeCrossStructure] = []
        self.max_memory_size = 100  # 最大100フレーム保持

        # デーモン制御
        self.running = False
        self.input_queue: queue.Queue = queue.Queue()

        self.logger.info("✅ JCrossLearningDaemon初期化完了")

    def _register_emotion_crosses(self):
        """
        感情DNAの全Cross構造をグローバルレジストリに登録
        """
        self.logger.info("感情DNAのCross構造を登録中...")

        multi_cross = self.emotion_system.multi_cross

        # Layer 0: Homeostasis (記憶系)
        for name in self.emotion_system.homeostasis_crosses.keys():
            if name in multi_cross.crosses:
                self.registry.register(name, multi_cross.crosses[name], group="memory")

        # Layer 1: Neurotransmitters (感情系)
        for name in self.emotion_system.neurotransmitter_crosses.keys():
            if name in multi_cross.crosses:
                self.registry.register(name, multi_cross.crosses[name], group="emotion")

        # Layer 2: Emotions (感情系)
        for name in self.emotion_system.emotion_crosses.keys():
            if name in multi_cross.crosses:
                self.registry.register(name, multi_cross.crosses[name], group="emotion")

        self.logger.info(f"✅ {len(self.registry.crosses)}個のCross構造を登録")

    def process_image_frame(self, image: Image.Image) -> Dict[str, Any]:
        """
        画像フレームを処理

        Args:
            image: PIL Image

        Returns:
            処理結果辞書
        """
        start_time = time.time()

        # Phase 8: 画像→Cross構造変換
        image_cross = self.image_converter.convert(image)

        self.logger.debug(f"画像→Cross変換完了: {image_cross}")

        # Cross記憶バンクに追加
        self.cross_memory_bank.append(image_cross)
        if len(self.cross_memory_bank) > self.max_memory_size:
            self.cross_memory_bank.pop(0)

        # 過去のCrossと同調度を計算
        sync_scores = []
        if len(self.cross_memory_bank) > 1:
            for i, past_cross in enumerate(self.cross_memory_bank[-10:]):  # 直近10フレーム
                if past_cross != image_cross:
                    sync = image_cross.sync_with(past_cross, layer=4)  # Concept Layerで比較
                    sync_scores.append(sync)

        avg_sync = np.mean(sync_scores) if sync_scores else 0.0

        # Phase 3: 感情判定
        # 簡易実装: 同調度が低い→新規性高い→好奇心
        #           同調度が高い→予測成功→喜び

        # 生理的状態
        physiological_state = {
            "体温": 37.0,
            "血圧": 120.0,
            "心拍数": 70.0,
            "血糖値": 100.0,
            "痛み": 0.0,
            "エネルギー": 0.8
        }

        # 認知的状態
        cognitive_state = {
            "新規性": 1.0 - avg_sync,  # 同調度が低い = 新規性高い
            "予測成功": avg_sync,       # 同調度が高い = 予測成功
            "予測失敗": 1.0 - avg_sync,
            "学習成功": avg_sync * 0.8,
            "理解": avg_sync * 0.7
        }

        # 感情判定を実行
        emotion_cross = self.emotion_system.determine_emotion(
            physiological_state,
            cognitive_state
        )

        # 感情名と強度を取得
        emotion_name = self.emotion_system.current_emotion_name
        emotion_intensity = self.emotion_system.current_emotion_intensity

        # Phase 4 + Stage 2: 感情が発火したら全ノード同調
        if emotion_name != "なし":
            # Stage 2: .jcrossから自動抽出
            allocation = self.emotion_system.get_resource_allocation()
            sync_mode = self.emotion_system.get_sync_mode()

            # 全ノード同調を発動
            self.registry.emotion_interrupt(
                emotion_name=emotion_name,
                resource_allocation=allocation,
                sync_mode=sync_mode
            )

        # 処理時間
        elapsed = time.time() - start_time

        # 学習履歴に追加
        result = {
            "frame": self.frame_count,
            "timestamp": datetime.now().isoformat(),
            "sync_score": float(avg_sync),
            "emotion": emotion_name,
            "emotion_intensity": emotion_intensity,
            "physiological_state": physiological_state,
            "cognitive_state": cognitive_state,
            "processing_time_ms": elapsed * 1000,
            "memory_bank_size": len(self.cross_memory_bank)
        }

        self.learning_history.append(result)
        self.frame_count += 1

        # ログ出力
        self.logger.info(
            f"Frame {self.frame_count}: "
            f"同調={avg_sync:.3f}, "
            f"感情={emotion_name}({emotion_intensity:.2f}), "
            f"{elapsed*1000:.1f}ms"
        )

        return result

    def save_learning_history(self):
        """
        学習履歴をJSON形式で保存
        """
        history_file = self.log_dir / f"learning_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(self.learning_history, f, ensure_ascii=False, indent=2)

        self.logger.info(f"学習履歴を保存: {history_file}")

    def run_interactive(self):
        """
        対話モードで実行

        ユーザーが画像パスを入力すると処理
        """
        self.logger.info("=== 対話モード開始 ===")
        self.logger.info("画像パスを入力してください（終了: quit）")

        self.running = True

        try:
            while self.running:
                try:
                    image_path = input("\n画像パス> ").strip()

                    if image_path.lower() in ["quit", "exit", "q"]:
                        break

                    if not image_path:
                        continue

                    # 画像を読み込み
                    image_path_obj = Path(image_path)

                    if not image_path_obj.exists():
                        self.logger.warning(f"ファイルが見つかりません: {image_path}")
                        continue

                    image = Image.open(image_path_obj)

                    # 処理
                    result = self.process_image_frame(image)

                    # 結果表示
                    print(f"\n--- 処理結果 ---")
                    print(f"同調度: {result['sync_score']:.3f}")
                    print(f"感情: {result['emotion']} (強度: {result['emotion_intensity']:.2f})")
                    print(f"生理状態: {result['physiological_state']}")
                    print(f"認知状態: {result['cognitive_state']}")
                    print(f"処理時間: {result['processing_time_ms']:.1f}ms")

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    self.logger.error(f"エラー: {e}", exc_info=True)

        finally:
            self.running = False
            self.save_learning_history()
            self.logger.info("対話モード終了")

    def run_test_mode(self, num_frames: int = 10):
        """
        テストモード: ランダム画像で動作確認

        Args:
            num_frames: テストフレーム数
        """
        self.logger.info(f"=== テストモード開始 ({num_frames}フレーム) ===")

        for i in range(num_frames):
            # ランダム画像を生成
            random_image = Image.fromarray(
                (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
            )

            # 処理
            result = self.process_image_frame(random_image)

            time.sleep(0.1)  # 少し待つ

        self.save_learning_history()
        self.logger.info("テストモード終了")

    def get_status(self) -> Dict[str, Any]:
        """
        現在のステータスを取得

        Returns:
            ステータス辞書
        """
        return {
            "frame_count": self.frame_count,
            "memory_bank_size": len(self.cross_memory_bank),
            "registry_status": self.registry.get_status(),
            "learning_history_size": len(self.learning_history)
        }


def main():
    """メイン関数"""
    print("=" * 80)
    print(".jcrossフル実装学習デーモン")
    print("Phase 1-9 統合版")
    print("=" * 80)
    print()

    # デーモンを作成
    daemon = JCrossLearningDaemon(
        use_gpu=False,  # GPU無効（CuPy未インストール）
        log_dir=str(Path.home() / ".verantyx" / "learning_logs")
    )

    print()
    print("モード選択:")
    print("1. テストモード（ランダム画像10フレーム）")
    print("2. 対話モード（画像パス入力）")
    print()

    mode = input("選択 (1/2)> ").strip()

    if mode == "1":
        daemon.run_test_mode(num_frames=10)
    elif mode == "2":
        daemon.run_interactive()
    else:
        print("テストモードを実行")
        daemon.run_test_mode(num_frames=10)

    # ステータス表示
    print()
    print("=" * 80)
    print("最終ステータス")
    print("=" * 80)
    status = daemon.get_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
