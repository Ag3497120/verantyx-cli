#!/usr/bin/env python3
"""
World Truth Learning Runner
世界の真理学習ランナー

物理シミュレーションを実行して世界の法則を学習する。

使い方:
    # 全ての基本真理を学習
    python -m verantyx_cli.vision.run_truth_learning

    # 特定の真理のみ学習
    python -m verantyx_cli.vision.run_truth_learning --truth falling
"""

import sys
from pathlib import Path
from typing import Dict, Any
import argparse

from verantyx_cli.vision.cross_physics_simulator import (
    create_falling_ball_simulation,
    create_projectile_simulation,
    create_horizontal_motion_simulation
)
from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank


def learn_falling_truth(memory_bank: WorldTruthMemoryBank) -> bool:
    """落下真理を学習"""
    print("\n" + "=" * 70)
    print("🍎 落下真理を学習")
    print("=" * 70)

    try:
        # シミュレーション実行
        timeline = create_falling_ball_simulation(
            duration=2.0,
            initial_height=1.0,
            gravity=9.8,
            restitution=0.8
        )

        # 真理として学習
        memory_bank.learn_truth("falling", timeline)

        return True

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def learn_horizontal_motion_truth(memory_bank: WorldTruthMemoryBank) -> bool:
    """水平運動真理を学習"""
    print("\n" + "=" * 70)
    print("➡️  水平運動真理を学習")
    print("=" * 70)

    try:
        timeline = create_horizontal_motion_simulation(
            duration=2.0,
            velocity=1.0
        )

        memory_bank.learn_truth("horizontal_motion", timeline)

        return True

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def learn_projectile_truth(memory_bank: WorldTruthMemoryBank) -> bool:
    """放物運動真理を学習"""
    print("\n" + "=" * 70)
    print("⚾ 放物運動真理を学習")
    print("=" * 70)

    try:
        timeline = create_projectile_simulation(
            duration=2.0,
            initial_velocity_x=1.0,
            initial_velocity_y=1.0,
            gravity=9.8
        )

        memory_bank.learn_truth("projectile", timeline)

        return True

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="World Truth Learning Runner - 世界の真理学習"
    )

    parser.add_argument(
        "--truth",
        type=str,
        help="学習する真理（指定しない場合は全真理）",
        choices=["falling", "horizontal_motion", "projectile"]
    )

    parser.add_argument(
        "--memory-path",
        type=str,
        help="記憶バンクの保存先（デフォルト: ~/.verantyx/world_truth_memory.json）"
    )

    args = parser.parse_args()

    # 記憶バンクのパス
    if args.memory_path:
        memory_path = Path(args.memory_path).expanduser().absolute()
    else:
        memory_path = Path.home() / ".verantyx" / "world_truth_memory.json"

    # 記憶バンクを初期化
    memory_bank = WorldTruthMemoryBank(memory_path=memory_path)

    print()
    print("=" * 70)
    print("🌍 World Truth Learning - 世界の真理学習")
    print("=" * 70)
    print(f"記憶バンク: {memory_path}")
    print("=" * 70)

    # 学習する真理を決定
    if args.truth:
        truths_to_learn = [args.truth]
    else:
        # デフォルト: 全ての基本真理
        truths_to_learn = ["falling", "horizontal_motion", "projectile"]

    print(f"\n学習する真理: {', '.join(truths_to_learn)}")

    # 各真理を学習
    results = {}

    for truth in truths_to_learn:
        if truth == "falling":
            success = learn_falling_truth(memory_bank)
        elif truth == "horizontal_motion":
            success = learn_horizontal_motion_truth(memory_bank)
        elif truth == "projectile":
            success = learn_projectile_truth(memory_bank)
        else:
            success = False

        results[truth] = success

    # 結果サマリー
    print("\n" + "=" * 70)
    print("📊 学習結果サマリー")
    print("=" * 70)

    for truth, success in results.items():
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"  {truth}: {status}")

    # 記憶バンクを保存
    memory_bank.save()

    # 学習済み真理の一覧を表示
    print("\n" + "=" * 70)
    print("💾 学習済み世界の真理一覧")
    print("=" * 70)

    truths = memory_bank.list_truths()

    for truth_info in truths:
        print(f"  - {truth_info['name']}")
        print(f"    期間: {truth_info['duration']:.2f}秒")
        print(f"    フレーム数: {truth_info['num_frames']}")
        print(f"    学習日時: {truth_info['learned_at']}")
        print()

    print("=" * 70)

    # 成功した真理があればexit code 0
    if any(results.values()):
        print("\n✅ 世界の真理学習が完了しました")
        print("\n次のステップ:")
        print("  1. 動画を分析する際、これらの真理が自動的に適用されます")
        print("  2. 動画内で「落下」「水平移動」「放物運動」が検出されます")
        print("  3. より高精度な形状・動き認識が可能になります")
        print()
        return 0
    else:
        print("\n❌ すべての真理学習が失敗しました")
        return 1


if __name__ == "__main__":
    sys.exit(main())
