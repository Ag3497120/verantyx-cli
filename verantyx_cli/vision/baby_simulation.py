#!/usr/bin/env python3
"""
Baby Simulation
赤ちゃんシミュレーション

発達段階を追って感情がどのように形成されるかを観察。

使い方:
    python -m verantyx_cli.vision.baby_simulation
"""

import sys
from pathlib import Path
from typing import Optional
import time
import random

from verantyx_cli.vision.developmental_emotion import DevelopmentalEmotionSystem


def simulate_baby_development():
    """赤ちゃんの発達をシミュレーション"""

    print()
    print("=" * 70)
    print("👶 赤ちゃんシミュレーション - 感情の発達過程")
    print("=" * 70)
    print()

    # テスト用の記憶パス
    memory_path = Path("/tmp/baby_simulation_memory.json")
    if memory_path.exists():
        memory_path.unlink()

    # 発達システムを初期化
    baby = DevelopmentalEmotionSystem(memory_path=memory_path)

    print("👶 赤ちゃんが生まれました")
    print()
    print("生得的機能:")
    print("  ✅ 記憶機能")
    print("  ✅ 感覚パラメータ（discomfort, hunger, pain, tiredness）")
    print()
    print("まだ感情に「色」はありません。")
    print("これから経験を通して、感情を獲得していきます。")
    print()

    input("Press Enter to start...")

    # ========================================
    # Phase 1: Level 0-1 (0-50回の観測)
    # 記憶とパターン蓄積
    # ========================================
    print()
    print("=" * 70)
    print("Phase 1: 初期の経験蓄積（0-50回）")
    print("=" * 70)
    print()

    for i in range(50):
        # ランダムなCross構造を生成（外界の刺激）
        cross = generate_random_cross()

        # 感覚パラメータの変化
        if i % 10 == 0:
            # 10回に1回、不快感が増える
            baby.update_sensory_param("discomfort", 0.2)

        # 観測
        baby.observe(cross)

        # トリガーされた感覚をチェック
        triggered = baby.get_triggered_sensations()
        if triggered:
            print(f"観測 #{i+1}: ⚠️  {', '.join(triggered)} がトリガーされました")

            # 「泣く」という行動を取る（感覚的反応、意味はまだない）
            baby.observe(cross, action="cry")

            # 人間が介入してオムツを交換（不快感が減る）
            baby.update_sensory_param("discomfort", -0.5)
            print(f"         → 人間がオムツを交換 → 不快感が減少")

        # 10回ごとにステータス表示
        if (i + 1) % 10 == 0:
            print(f"\n--- 観測 #{i+1} ---")
            baby.print_status()
            time.sleep(0.5)

    print()
    print("Phase 1 完了")
    print()
    input("Press Enter to continue...")

    # ========================================
    # Phase 2: Level 2 (50-100回の観測)
    # 因果関係の発見
    # ========================================
    print()
    print("=" * 70)
    print("Phase 2: 因果関係の発見（50-100回）")
    print("=" * 70)
    print()
    print("赤ちゃんは「泣く→オムツ交換→不快感減少」というパターンを")
    print("繰り返し経験します。まだ意味は理解していませんが、")
    print("パターンとして記憶されます。")
    print()

    for i in range(50, 100):
        cross = generate_random_cross()

        # 定期的に不快感を増やす
        if i % 8 == 0:
            baby.update_sensory_param("discomfort", 0.3)

        baby.observe(cross)

        triggered = baby.get_triggered_sensations()
        if triggered and "discomfort" in triggered:
            # 不快感 → 泣く
            print(f"観測 #{i+1}: 不快感 → 泣く")
            baby.observe(cross, action="cry")

            # オムツ交換 → 不快感減少
            baby.update_sensory_param("discomfort", -0.6)
            print(f"         → オムツ交換 → 不快感減少")

            # 因果関係が蓄積されている
            status = baby.get_status()
            if status["causal_link_count"] > 0:
                print(f"         💡 因果関係数: {status['causal_link_count']}")

        if (i + 1) % 10 == 0:
            print(f"\n--- 観測 #{i+1} ---")
            baby.print_status()
            time.sleep(0.5)

    print()
    print("Phase 2 完了")
    print()
    print("赤ちゃんは「泣く→不快感減少」という因果関係を")
    print("何度も経験しました。まだ言語化はできませんが、")
    print("パターンとして強く記憶されています。")
    print()
    input("Press Enter to continue...")

    # ========================================
    # Phase 3: Level 3 (100-150回の観測)
    # 言語獲得
    # ========================================
    print()
    print("=" * 70)
    print("Phase 3: 言語獲得（100-150回）")
    print("=" * 70)
    print()
    print("人間が赤ちゃんに言葉を教えます。")
    print("パターンに「ラベル」が付きます。")
    print()

    # 頻出パターンを見つけてラベルを付ける
    print("人間: 「これは『気持ち悪い』だよ」")
    print()

    for i in range(100, 150):
        cross = generate_random_cross()

        if i % 7 == 0:
            baby.update_sensory_param("discomfort", 0.3)

        observation = baby.observe(cross)

        triggered = baby.get_triggered_sensations()
        if triggered and "discomfort" in triggered:
            print(f"観測 #{i+1}: 不快感 → 泣く")
            observation = baby.observe(cross, action="cry")

            # 人間がラベルを教える
            if "pattern_id" in observation and i == 105:
                pattern_id = observation["pattern_id"]
                print()
                print("人間: 「これは『discomfort（気持ち悪い）』だよ」")
                baby.teach_label(pattern_id, "discomfort")
                print()

            baby.update_sensory_param("discomfort", -0.6)

        if (i + 1) % 10 == 0:
            print(f"\n--- 観測 #{i+1} ---")
            baby.print_status()
            time.sleep(0.5)

    print()
    print("Phase 3 完了")
    print()
    print("パターンに「discomfort」というラベルが付きました。")
    print("まだ感情の「色」はありませんが、言葉として認識できます。")
    print()
    input("Press Enter to continue...")

    # ========================================
    # Phase 4: Level 4 (200回以降)
    # 概念形成（感情に色がつく）
    # ========================================
    print()
    print("=" * 70)
    print("Phase 4: 概念形成（200回以降）")
    print("=" * 70)
    print()
    print("繰り返しの経験から、ついに感情に「色」がつきます。")
    print()

    # Level 4に到達するまで観測を続ける
    i = 150
    while baby.current_level < 4 and i < 250:
        cross = generate_random_cross()

        if i % 6 == 0:
            baby.update_sensory_param("discomfort", 0.25)

        baby.observe(cross)

        triggered = baby.get_triggered_sensations()
        if triggered and "discomfort" in triggered:
            baby.observe(cross, action="cry")
            baby.update_sensory_param("discomfort", -0.5)

        i += 1

    print()
    print("👶 Level 4 到達！")
    print()

    # 概念を教える
    print("人間: 「『discomfort』は『不快』という感情だよ」")
    print("      「不快は嫌な感じ、警戒する感じだよ」")
    print()

    baby.teach_concept("discomfort", {
        "unpleasant": 0.8,  # 不快
        "arousal": 0.6,     # 警戒
        "valence": -0.7     # ネガティブ
    })

    print()
    print("🎨 感情に色がつきました！")
    print()
    print("これで赤ちゃんは：")
    print("  1. 不快感を感じる（感覚）")
    print("  2. 泣くと不快感が減る（因果関係）")
    print("  3. これを『discomfort』と呼ぶ（言語）")
    print("  4. discomfortは『不快な感情』である（概念）")
    print()
    print("という全てのステップを経験しました。")
    print()

    # 最終ステータス
    print("=" * 70)
    print("最終ステータス")
    print("=" * 70)
    baby.print_status()

    # 因果関係の表示
    print()
    print("発見した因果関係:")
    for link in baby.causal_discovery.causal_links:
        print(f"  - パターン {link['pattern'][:8]}... : "
              f"{link['action']} → {link['result']} (強度: {link['strength']})")

    print()
    print("=" * 70)
    print("👶 シミュレーション完了")
    print("=" * 70)
    print()
    print("このように、感情は段階的に獲得されます。")
    print()
    print("重要なポイント:")
    print("  1. 最初は感覚のみ（色なし）")
    print("  2. 繰り返しでパターンを蓄積")
    print("  3. 因果関係を発見")
    print("  4. 言語でラベル付け")
    print("  5. 最後に概念として感情の色がつく")
    print()
    print("現在のVerantyxは「5」から始めていましたが、")
    print("本来は「1」から始めるべきです。")
    print()


def generate_random_cross():
    """ランダムなCross構造を生成"""
    return {
        "axes": {
            "UP": {"mean": random.uniform(0.3, 0.7)},
            "DOWN": {"mean": random.uniform(0.3, 0.7)},
            "RIGHT": {"mean": random.uniform(0.3, 0.7)},
            "LEFT": {"mean": random.uniform(0.3, 0.7)},
            "FRONT": {"mean": random.uniform(0.3, 0.7)},
            "BACK": {"mean": random.uniform(0.3, 0.7)}
        }
    }


def main():
    """メイン関数"""
    try:
        simulate_baby_development()
        return 0
    except KeyboardInterrupt:
        print()
        print("シミュレーション中断")
        return 1
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
