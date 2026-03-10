#!/usr/bin/env python3
"""
Interactive Developmental AI Test
インタラクティブな発達段階AIテスト

ユーザーが直接、発達段階システムを体験できるインタラクティブツール
"""

import sys
from pathlib import Path
from typing import Dict, Any
from PIL import Image
import numpy as np

from verantyx_cli.engine.jcross_bootstrap import ZeroYearOldJCross
from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter
from verantyx_cli.vision.developmental_processors import DevelopmentalStageSystem
from verantyx_cli.vision.cognitive_discomfort_processors import CognitiveDiscomfortSystem
from verantyx_cli.vision.emotion_dna_processors import EmotionDNASystem


class InteractiveDevelopmentalTest:
    """
    インタラクティブな発達段階テスト
    """

    def __init__(self):
        """Initialize"""
        print()
        print("=" * 80)
        print("🧠 Verantyx 発達段階AI - インタラクティブテスト")
        print("=" * 80)
        print()

        # システム初期化
        print("システム初期化中...")
        self.baby = ZeroYearOldJCross()
        self.converter = MultiLayerCrossConverter(quality="fast")
        self.developmental_system = DevelopmentalStageSystem(growth_speed=1000.0)
        self.cognitive_discomfort = CognitiveDiscomfortSystem()
        self.emotion_dna = EmotionDNASystem()

        # 予測履歴（予測誤差計算用）
        self.prediction_history = []

        print("✅ 初期化完了")
        print()

    def show_current_status(self):
        """現在の状態を表示"""
        status = self.developmental_system.get_status()

        print()
        print("=" * 80)
        print("📊 現在の発達状態")
        print("=" * 80)
        print()
        print(f"年齢: {status['年齢']:.4f}歳 (約{status['年齢']*365:.0f}日)")
        print(f"段階: {status['段階']}")
        print(f"運動能力: {status['運動能力']}")
        print(f"空間記憶: {'有効' if status['空間記憶'] else '無効'}")
        print(f"記憶形式: {status['記憶形式']}")
        print(f"経験形式: {status['経験形式']}")
        print()
        print(f"説明: {status['説明']}")
        print()

        # 記憶統計
        baby_status = self.baby.get_status()
        print(f"総経験数: {baby_status['記憶']['総経験数']}")
        print()
        print("=" * 80)
        print()

    def process_image(self, image_path: str):
        """画像を処理"""
        image_path = Path(image_path).expanduser()

        if not image_path.exists():
            print(f"❌ ファイルが見つかりません: {image_path}")
            return

        print()
        print("-" * 80)
        print(f"🖼️  画像処理: {image_path.name}")
        print("-" * 80)
        print()

        # 画像読み込み
        try:
            img = Image.open(image_path)
            print(f"画像サイズ: {img.size}")
            print()
        except Exception as e:
            print(f"❌ 画像の読み込みに失敗: {e}")
            return

        # Cross構造に変換
        print("Cross構造に変換中...")
        cross_structure = self.converter.convert(img)

        total_points = cross_structure['metadata']['total_points']
        print(f"✅ 変換完了: {total_points}点")
        print()

        # 発達段階に応じた処理
        print("発達段階に応じた処理...")

        # 年齢を更新（画像1枚 = 0.1秒の経験）
        elapsed = 0.1
        new_stage = self.developmental_system.update_age(elapsed)

        # 予測誤差を計算
        prediction_error = self._calculate_prediction_error(cross_structure)

        # 類似経験数を取得
        similar_count = len(self.baby._find_similar_experiences(cross_structure, threshold=0.5))

        # 同調失敗度を計算（簡易版）
        sync_failure = 1.0 - (similar_count / 10.0) if similar_count < 10 else 0.0

        # 認知的不快感を計算
        cognitive_discomfort = self.cognitive_discomfort.calculate_total_cognitive_discomfort(
            cross_structure=cross_structure,
            prediction_error=prediction_error,
            similar_experiences_count=similar_count,
            sync_failure=sync_failure
        )

        # 認知的快感を計算
        cognitive_pleasure = self.cognitive_discomfort.calculate_total_cognitive_pleasure(
            prediction_error=prediction_error,
            similar_experiences_count=similar_count,
            sync_degree=1.0 - sync_failure
        )

        # 生理的不快感
        physiological_discomfort_info = self.baby._calc_total_discomfort()
        physiological_discomfort = physiological_discomfort_info["総不快感"]

        # 総合不快感
        current_stage = self.developmental_system.get_status()['段階']
        total_discomfort = self.cognitive_discomfort.calculate_total_discomfort(
            physiological_discomfort=physiological_discomfort,
            cognitive_discomfort=cognitive_discomfort,
            developmental_stage=current_stage
        )

        # 感情DNA処理: イベント処理（神経伝達物質の放出）
        self.emotion_dna.process_event(
            prediction_error=prediction_error,
            similar_experiences_count=similar_count,
            sync_degree=1.0 - sync_failure,
            discomfort_decreased=(total_discomfort < 0.3),
            new_pattern_found=(similar_count == 0)
        )

        # 感情DNA処理: 感情の判定
        physiological_state = {
            "pain": physiological_discomfort_info.get("痛み", 0.0),
            "critical_deviation": physiological_discomfort > 0.9,
            "energy": self.baby.state.get("エネルギー", 100.0),
            "all_deviation": physiological_discomfort
        }

        cognitive_state = {
            "total_discomfort": cognitive_discomfort,
            "resolution_failures": 0,  # 簡易版
            "novelty_discomfort": self.cognitive_discomfort.discomfort["novelty_discomfort"]
        }

        current_emotion = self.emotion_dna.determine_emotion(
            physiological_state=physiological_state,
            cognitive_state=cognitive_state
        )

        # 神経伝達物質の減衰
        self.emotion_dna.decay_neurotransmitters(decay_rate=0.1)

        # 基本経験データ
        experience = {
            "cross_structure": cross_structure,
            "discomfort": total_discomfort,
            "cognitive_discomfort": cognitive_discomfort,
            "cognitive_pleasure": cognitive_pleasure,
            "context": {
                "type": "interactive_test",
                "image": str(image_path)
            }
        }

        # 記憶に感情の色を付ける
        experience = self.emotion_dna.add_color_to_memory(experience)

        # 記憶をアップグレード
        upgraded_experience = self.developmental_system.upgrade_memory(experience)

        # 結果表示
        print()
        print("📋 処理結果:")
        print(f"  総点数: {total_points}点")
        print()
        print("😣 不快感:")
        print(f"  総合不快感: {upgraded_experience['discomfort']:.2f}")
        print(f"  認知的不快: {upgraded_experience['cognitive_discomfort']:.2f}")

        # 不快感の詳細
        discomfort_status = self.cognitive_discomfort.get_status()
        print()
        print("  詳細:")
        print(f"    予測誤差不快: {discomfort_status['不快感']['予測誤差不快']:.2f}")
        print(f"    未知性不快: {discomfort_status['不快感']['未知性不快']:.2f}")
        print(f"    複雑性不快: {discomfort_status['不快感']['複雑性不快']:.2f}")
        print(f"    同調失敗不快: {discomfort_status['不快感']['同調失敗不快']:.2f}")

        print()
        print("😊 快感:")
        print(f"  総認知快感: {upgraded_experience['cognitive_pleasure']:.2f}")
        print(f"    予測成功快: {discomfort_status['快感']['予測成功快']:.2f}")
        print(f"    理解快: {discomfort_status['快感']['理解快']:.2f}")
        print(f"    同調快: {discomfort_status['快感']['同調快']:.2f}")

        # 解消アクション
        action = self.cognitive_discomfort.determine_discomfort_resolution_action()
        if action['priority'] > 0.5:
            print()
            print(f"🎯 推奨アクション: {action['action']}")
            print(f"   理由: {action['reason']}")

        # 感情DNA状態表示
        emotion_status = self.emotion_dna.get_status()
        print()
        print("🎨 感情状態:")
        print(f"  支配的感情: {self.emotion_dna.get_emotion_japanese()}")
        print(f"  感情強度: {current_emotion['intensity']:.2f}")
        print(f"  感情の色: {self.emotion_dna.get_emotion_color_name()}")
        print(f"  ノード同調: {current_emotion['node_synchronization']}")
        print()
        print("  神経伝達物質:")
        print(f"    ドーパミン: {emotion_status['neurotransmitters']['dopamine']:.2f} (快)")
        print(f"    ノルアドレナリン: {emotion_status['neurotransmitters']['noradrenaline']:.2f} (不快・緊張)")
        print(f"    セロトニン: {emotion_status['neurotransmitters']['serotonin']:.2f} (安心)")
        print()
        print("  リソース配分:")
        for resource, allocation in current_emotion['resource_allocation'].items():
            print(f"    {resource}: {allocation:.2f}")

        # 空間情報があれば表示
        if 'spatial' in upgraded_experience:
            spatial = upgraded_experience['spatial']
            print()
            print("📍 空間記憶（NEW!）:")
            print(f"  X: {spatial['X']:.2f}")
            print(f"  Y: {spatial['Y']:.2f} (目線の高さ)")
            print(f"  Z: {spatial['Z']:.2f}")
            if 'type' in spatial:
                print(f"  タイプ: {spatial['type']}")

        # 軌跡情報があれば表示
        if 'trajectory' in upgraded_experience:
            trajectory = upgraded_experience['trajectory']
            print()
            print("🚶 移動軌跡:")
            print(f"  ΔX: {trajectory['X']:.2f}")
            print(f"  ΔY: {trajectory['Y']:.2f}")
            print(f"  ΔZ: {trajectory['Z']:.2f}")

        # カテゴリ情報があれば表示
        if 'category' in upgraded_experience and upgraded_experience['category'] is not None:
            print()
            print(f"🏷️  カテゴリ: {upgraded_experience['category']}")

        # 予測履歴に追加
        self.prediction_history.append({
            'total_points': total_points,
            'cross_structure': cross_structure
        })
        if len(self.prediction_history) > 10:
            self.prediction_history.pop(0)

        # 記憶に保存
        self.baby._store_experience(
            cross_structure=cross_structure,
            discomfort=upgraded_experience["discomfort"],
            context=upgraded_experience["context"]
        )

        print()
        print("✅ 記憶に保存しました")
        print()

        # 段階変更チェック
        current_status = self.developmental_system.get_status()
        if current_status['段階'] != new_stage:
            print()
            print("🎉" * 20)
            print(f"🎂 おめでとうございます！ {new_stage} に到達しました！")
            print("🎉" * 20)
            print()

    def process_video(self, video_path: str, max_frames: int = 10):
        """動画を処理"""
        import cv2

        video_path = Path(video_path).expanduser()

        if not video_path.exists():
            print(f"❌ ファイルが見つかりません: {video_path}")
            return

        print()
        print("-" * 80)
        print(f"🎬 動画処理: {video_path.name}")
        print("-" * 80)
        print()

        # 動画を開く
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"❌ 動画を開けませんでした")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        print(f"動画情報:")
        print(f"  総フレーム: {total_frames}")
        print(f"  FPS: {fps:.2f}")
        print(f"  処理予定: {max_frames}フレーム")
        print()

        # フレーム処理
        skip_interval = max(1, total_frames // max_frames)
        frame_count = 0
        processed_count = 0

        while processed_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # スキップ
            if (frame_count - 1) % skip_interval != 0:
                continue

            # BGR → RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)

            # Cross構造変換
            cross_structure = self.converter.convert(frame_pil)

            # 年齢更新
            new_stage = self.developmental_system.update_age(0.1)

            # 記憶アップグレード
            discomfort_info = self.baby._calc_total_discomfort()
            experience = {
                "cross_structure": cross_structure,
                "discomfort": discomfort_info["総不快感"],
                "context": {
                    "type": "interactive_video",
                    "frame": frame_count
                }
            }

            upgraded_experience = self.developmental_system.upgrade_memory(experience)

            # 保存
            self.baby._store_experience(
                cross_structure=cross_structure,
                discomfort=upgraded_experience["discomfort"],
                context=upgraded_experience["context"]
            )

            processed_count += 1

            # 進捗表示
            if processed_count % 5 == 0 or processed_count == max_frames:
                print(f"  処理中: {processed_count}/{max_frames}フレーム")

        cap.release()

        print()
        print(f"✅ 完了: {processed_count}フレーム処理")
        print()

    def age_up(self, target_age: float):
        """年齢を直接設定（テスト用）"""
        print()
        print(f"⏩ 年齢を {target_age}歳に設定します...")
        print()

        # 必要な経験時間を計算
        seconds_per_year = 365.25 * 24 * 3600
        target_experience_time = (target_age * seconds_per_year) / self.developmental_system.state["growth_speed"]

        # 現在の経験時間
        current_time = self.developmental_system.state.get("experience_time", 0.0)

        # 差分を加算
        elapsed = target_experience_time - current_time

        if elapsed > 0:
            new_stage = self.developmental_system.update_age(elapsed)
            print(f"✅ {target_age}歳（{new_stage}）に到達しました！")
        else:
            print(f"⚠️  既に{target_age}歳を超えています")

        self.show_current_status()

    def _calculate_prediction_error(self, current_cross: Dict[str, Any]) -> float:
        """
        予測誤差を計算

        Args:
            current_cross: 現在のCross構造

        Returns:
            予測誤差 (0.0-1.0)
        """
        if len(self.prediction_history) < 2:
            # 予測不可能（履歴が少ない）
            return 0.5

        # 前2つから予測
        prev_prev = self.prediction_history[-2]['total_points']
        prev = self.prediction_history[-1]['total_points']
        current = current_cross['metadata']['total_points']

        # 簡易予測: 前回の差分を使う
        diff = prev - prev_prev
        predicted = prev + diff

        # 誤差
        error = abs(predicted - current) / max(1, current)

        return min(1.0, error)

    def interactive_menu(self):
        """インタラクティブメニュー"""
        while True:
            print()
            print("=" * 80)
            print("📋 メニュー")
            print("=" * 80)
            print()
            print("1. 現在の状態を表示")
            print("2. 画像を処理")
            print("3. 動画を処理")
            print("4. 年齢を設定（テスト用）")
            print("5. 終了")
            print()

            choice = input("選択してください (1-5): ").strip()

            if choice == "1":
                self.show_current_status()

            elif choice == "2":
                print()
                image_path = input("画像パスを入力: ").strip()
                self.process_image(image_path)

            elif choice == "3":
                print()
                video_path = input("動画パスを入力: ").strip()
                max_frames = input("処理フレーム数（デフォルト10）: ").strip()
                max_frames = int(max_frames) if max_frames else 10
                self.process_video(video_path, max_frames)

            elif choice == "4":
                print()
                print("年齢設定:")
                print("  1: 1歳（空間記憶解禁）")
                print("  3: 3歳（移動軌跡解禁）")
                print("  7: 7歳（カテゴリ学習解禁）")
                print("  18: 18歳（メタ認知解禁）")
                age_choice = input("年齢を入力: ").strip()
                try:
                    target_age = float(age_choice)
                    self.age_up(target_age)
                except ValueError:
                    print("❌ 無効な入力")

            elif choice == "5":
                print()
                print("👋 終了します")
                print()
                break

            else:
                print("❌ 無効な選択")


def main():
    """メイン関数"""
    tester = InteractiveDevelopmentalTest()

    # 初期状態表示
    tester.show_current_status()

    # インタラクティブメニュー
    tester.interactive_menu()

    return 0


if __name__ == "__main__":
    sys.exit(main())
