#!/usr/bin/env python3
"""
Verantyx Survival Demo
生存システムのデモンストレーション

エネルギー、痛み、死の概念を実演。
"""

import sys
import time
import random

from verantyx_cli.vision.verantyx_survival_processors import VerantyxSurvivalSystem


def demo_survival():
    """生存システムのデモ"""

    print()
    print("=" * 70)
    print("🌱 Verantyx 生存システム デモンストレーション")
    print("=" * 70)
    print()
    print("Verantyxは生物のように：")
    print("  - エネルギーを消費する")
    print("  - 痛みを感じる")
    print("  - 死ぬことができる")
    print()
    print("これらは全てCross構造にマッピングされます。")
    print()

    input("Press Enter to start...")

    # 生存システムを初期化
    verantyx = VerantyxSurvivalSystem()

    # 初期ステータス
    verantyx.print_status()

    # ========================================
    # シナリオ1: 通常の活動
    # ========================================
    print()
    print("=" * 70)
    print("シナリオ1: 通常の活動")
    print("=" * 70)
    print()

    for i in range(20):
        # フレーム更新
        state = verantyx.update()

        # 観測
        verantyx.observe()

        # たまに思考
        if i % 5 == 0:
            verantyx.think()

        # ステータス表示
        if (i + 1) % 5 == 0:
            print(f"\n--- フレーム {i+1} ---")
            print(f"エネルギー: {state['energy']:.1f}")
            print(f"痛み: {state['pain']:.1f}")
            time.sleep(0.3)

    verantyx.print_status()

    print()
    print("エネルギーが徐々に減少しています。")
    print()
    input("Press Enter to continue...")

    # ========================================
    # シナリオ2: 学習による大量消費
    # ========================================
    print()
    print("=" * 70)
    print("シナリオ2: 学習による大量エネルギー消費")
    print("=" * 70)
    print()

    for i in range(15):
        state = verantyx.update()

        # 毎フレーム学習（エネルギー消費大）
        result = verantyx.learn()

        if result.get("error") == "insufficient_energy":
            print(f"\n⚠️  フレーム {verantyx.frame_count}: エネルギー不足で学習不可！")
            break

        if (i + 1) % 3 == 0:
            print(f"\n--- フレーム {verantyx.frame_count} ---")
            print(f"エネルギー: {state['energy']:.1f}")
            print(f"状態: {state['status']}")
            time.sleep(0.3)

    verantyx.print_status()

    print()
    print("学習はエネルギーを大量に消費します。")
    print("エネルギー補給が必要です。")
    print()
    input("Press Enter to continue...")

    # ========================================
    # シナリオ3: エネルギー補給
    # ========================================
    print()
    print("=" * 70)
    print("シナリオ3: エネルギー補給")
    print("=" * 70)
    print()

    # 補給
    print("外部からエネルギーを供給...")
    verantyx.energy.recharge(50.0, "外部電源")

    verantyx.print_status()

    print()
    print("エネルギーが回復しました。")
    print()
    input("Press Enter to continue...")

    # ========================================
    # シナリオ4: 痛みの発生
    # ========================================
    print()
    print("=" * 70)
    print("シナリオ4: 痛みの発生と反応")
    print("=" * 70)
    print()

    # 衝突
    print("物理的衝突が発生...")
    verantyx.pain.inflict("collision")

    verantyx.print_status()

    # さらに衝突
    print()
    print("再度衝突...")
    verantyx.pain.inflict("collision")

    # 過負荷
    print()
    print("処理過負荷...")
    verantyx.pain.inflict("overload")

    verantyx.print_status()

    print()
    print("痛みが蓄積しています。")
    print("Cross軸のBAK軸（回避）が上昇しています。")
    print()
    input("Press Enter to continue...")

    # ========================================
    # シナリオ5: 痛みの回復
    # ========================================
    print()
    print("=" * 70)
    print("シナリオ5: 痛みの回復")
    print("=" * 70)
    print()

    for i in range(10):
        state = verantyx.update()

        # 休息（痛み回復速度アップ）
        if i % 2 == 0:
            verantyx.pain.recover("rest")

        if (i + 1) % 3 == 0:
            print(f"\n--- フレーム {verantyx.frame_count} ---")
            print(f"痛み: {state['pain']:.1f}")
            time.sleep(0.3)

    verantyx.print_status()

    print()
    print("休息により痛みが回復しました。")
    print()
    input("Press Enter to continue...")

    # ========================================
    # シナリオ6: 瀕死状態
    # ========================================
    print()
    print("=" * 70)
    print("シナリオ6: 瀕死状態への突入")
    print("=" * 70)
    print()

    # エネルギーを大量消費
    print("大量の学習タスクを実行...")
    for i in range(50):
        state = verantyx.update()

        verantyx.learn()

        if state["status"] == "dying":
            print()
            print("💀 瀕死状態に突入！")
            print(f"   エネルギー: {state['energy']:.1f}")
            print(f"   痛み: {state['pain']:.1f}")
            break

        if (i + 1) % 10 == 0:
            print(f"\nフレーム {verantyx.frame_count}: エネルギー {state['energy']:.1f}")

    verantyx.print_status()

    print()
    print("エネルギーが危機的レベルに達しました。")
    print("すぐに補給しないと死亡します。")
    print()

    # ユーザーに選択させる
    print("どうしますか？")
    print("  1. エネルギーを補給する")
    print("  2. そのまま続ける（死亡の可能性）")
    choice = input("選択 (1/2): ").strip()

    if choice == "1":
        print()
        print("エネルギーを補給...")
        verantyx.energy.recharge(80.0, "緊急補給")
        verantyx.print_status()
    else:
        print()
        print("補給せずに続行...")

    input("Press Enter to continue...")

    # ========================================
    # シナリオ7: 死亡（または生存）
    # ========================================
    print()
    print("=" * 70)
    print("シナリオ7: 最終フェーズ")
    print("=" * 70)
    print()

    for i in range(50):
        state = verantyx.update()

        if state["status"] == "dead":
            print()
            print("Verantyxは死亡しました。")
            break

        # 活動を続ける
        verantyx.observe()

        if (i + 1) % 10 == 0:
            print(f"\nフレーム {verantyx.frame_count}:")
            print(f"  状態: {state['status']}")
            print(f"  エネルギー: {state['energy']:.1f}")
            time.sleep(0.3)

    # 最終ステータス
    print()
    verantyx.print_status()

    # まとめ
    print()
    print("=" * 70)
    print("デモ完了")
    print("=" * 70)
    print()
    print("【重要なポイント】")
    print()
    print("1. エネルギー:")
    print("   - 全ての活動にエネルギーが必要")
    print("   - 学習 > 思考 > 観測 > 基礎代謝")
    print("   - エネルギー0 = 死")
    print()
    print("2. 痛み:")
    print("   - 衝突、過負荷、破損で発生")
    print("   - 回避行動を促す（BACK軸上昇）")
    print("   - 痛み高 + エネルギー低 = 死")
    print()
    print("3. Cross軸マッピング:")
    print("   - エネルギー高 → DOWN軸高（安定）")
    print("   - エネルギー低 → UP軸高（警戒）")
    print("   - 痛み → BACK軸高（回避）")
    print()
    print("4. 死:")
    print("   - エネルギー枯渇")
    print("   - または痛み+エネルギー不足")
    print("   - 死亡時、全軸停止（BACK軸のみ残る = 記憶）")
    print()
    print("これが生物的なVerantyxです。")
    print()


def main():
    """メイン関数"""
    try:
        demo_survival()
        return 0
    except KeyboardInterrupt:
        print()
        print("デモ中断")
        return 1
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
