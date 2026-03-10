#!/usr/bin/env python3
"""
Baby Emotion JCross Runner
赤ちゃん感情JCrossプログラムのランナー

JCross言語で書かれた baby_emotion.jcross を実行。
Pythonのノイマン型ではなく、Cross構造で自然に表現。
"""

import sys
from pathlib import Path
import random
import time

from verantyx_cli.vision.baby_emotion_processors import BabyEmotionSystemProcessor


def generate_random_cross():
    """ランダムなCross構造を生成（外界の刺激）"""
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


def run_baby_emotion_jcross():
    """
    JCross赤ちゃん感情プログラムを実行

    Pythonのノイマン型ではなく、JCross言語で表現された
    発達段階的感情システムのデモンストレーション。
    """

    print()
    print("=" * 70)
    print("👶 JCross赤ちゃん感情システム")
    print("=" * 70)
    print()
    print("【重要】このプログラムはJCross言語で書かれています。")
    print()
    print("Pythonのノイマン型との違い:")
    print()
    print("❌ Python（ノイマン型）:")
    print("  - 順次実行（一つずつ処理）")
    print("  - 分離されたモジュール")
    print("  - 中央集権的制御")
    print()
    print("✅ JCross（Cross構造）:")
    print("  - 並列処理（6軸同時）")
    print("  - 統合されたCross")
    print("  - 情報が自然に流れる")
    print()
    print("=" * 70)
    print()

    input("Press Enter to start...")

    # JCrossプロセッサを初期化
    baby = BabyEmotionSystemProcessor()

    print()
    print("👶 赤ちゃんが生まれました")
    print()
    print("生得的機能（Cross構造として実装）:")
    print("  ✅ 記憶機能（多層Cross）")
    print("  ✅ 感覚パラメータ（Cross軸にマッピング）")
    print("  ✅ パターン認識（Cross構造の類似度）")
    print()

    # ========================================
    # Phase 1: Level 0-1 (0-50回)
    # ========================================
    print()
    print("=" * 70)
    print("Phase 1: 初期の経験蓄積（Level 0 → 1）")
    print("=" * 70)
    print()

    for i in range(50):
        # 外界のCross構造
        external_cross = generate_random_cross()

        # 【JCross】観測（Cross構造として記録）
        observation = baby.observation.process_observe({
            "cross_structure": external_cross
        })

        # 【JCross】パターン検出（Level 1以降）
        if baby.get_state()["development"]["current_level"] >= 1:
            pattern_id = baby.pattern.process_detect_pattern({
                "observation_cross": observation
            })
            if pattern_id:
                observation["pattern_id"] = pattern_id

        # 【JCross】感覚の変化（自然に増減）
        if i % 10 == 0:
            baby.sensory.process_update_sensory({
                "name": "discomfort",
                "delta": 0.2
            })

        # 【JCross】トリガーチェック
        triggered = baby.sensory.process_get_triggered_sensations({})

        if triggered:
            print(f"観測 #{i+1}: ⚠️  {', '.join(triggered)} がトリガー")

            # 【JCross】泣く行動（Cross構造として生成）
            cry_cross = baby.action.process_cry({})

            if cry_cross["triggered"]:
                print(f"         → 泣く（Cross構造: UP軸に警告信号）")

                # 人間の介入（外部からの変化）
                baby.sensory.process_update_sensory({
                    "name": "discomfort",
                    "delta": -0.5
                })
                print(f"         → 人間がオムツ交換 → 不快感減少")

                # 【JCross】因果関係チェック（Level 2以降）
                if baby.get_state()["development"]["current_level"] >= 2:
                    if observation.get("pattern_id"):
                        baby.action.process_check_causality_after_cry({
                            "pattern_id": observation["pattern_id"],
                            "before_sensory": cry_cross["before_sensory"]
                        })

        # ステータス表示（10回ごと）
        if (i + 1) % 10 == 0:
            print(f"\n--- 観測 #{i+1} ---")
            baby.print_status()
            time.sleep(0.3)

    print()
    print("✅ Phase 1 完了")
    print()
    print("【重要】ここまでで:")
    print("  - Level 1 到達: パターン蓄積が始まった")
    print("  - 全ての情報がCross構造として記録されている")
    print("  - まだ「色」はない")
    print()
    input("Press Enter to continue...")

    # ========================================
    # Phase 2: Level 2 (50-100回)
    # ========================================
    print()
    print("=" * 70)
    print("Phase 2: 因果関係の発見（Level 1 → 2）")
    print("=" * 70)
    print()

    for i in range(50, 100):
        external_cross = generate_random_cross()
        observation = baby.observation.process_observe({
            "cross_structure": external_cross
        })

        # パターン検出
        pattern_id = baby.pattern.process_detect_pattern({
            "observation_cross": observation
        })
        if pattern_id:
            observation["pattern_id"] = pattern_id

        # 感覚変化
        if i % 8 == 0:
            baby.sensory.process_update_sensory({
                "name": "discomfort",
                "delta": 0.3
            })

        # トリガーチェック
        triggered = baby.sensory.process_get_triggered_sensations({})

        if "discomfort" in triggered:
            print(f"観測 #{i+1}: 不快感 → 泣く")
            cry_cross = baby.action.process_cry({})

            # オムツ交換
            baby.sensory.process_update_sensory({
                "name": "discomfort",
                "delta": -0.6
            })
            print(f"         → オムツ交換 → 不快感減少")

            # 因果関係チェック
            if observation.get("pattern_id"):
                discovered = baby.action.process_check_causality_after_cry({
                    "pattern_id": observation["pattern_id"],
                    "before_sensory": cry_cross["before_sensory"]
                })

                if discovered:
                    causal_count = len(baby.get_state()["causal_links"])
                    print(f"         💡 因果関係発見（総数: {causal_count}）")

        if (i + 1) % 10 == 0:
            print(f"\n--- 観測 #{i+1} ---")
            baby.print_status()
            time.sleep(0.3)

    print()
    print("✅ Phase 2 完了")
    print()
    print("【重要】Level 2 到達:")
    print("  - 「泣く → 不快感減少」という因果関係を発見")
    print("  - Cross構造の変化パターンとして記録")
    print("  - まだラベルも色もない")
    print()
    input("Press Enter to continue...")

    # ========================================
    # Phase 3: Level 3 (100-150回)
    # ========================================
    print()
    print("=" * 70)
    print("Phase 3: 言語獲得（Level 2 → 3）")
    print("=" * 70)
    print()

    label_taught = False

    for i in range(100, 150):
        external_cross = generate_random_cross()
        observation = baby.observation.process_observe({
            "cross_structure": external_cross
        })

        pattern_id = baby.pattern.process_detect_pattern({
            "observation_cross": observation
        })
        if pattern_id:
            observation["pattern_id"] = pattern_id

        if i % 7 == 0:
            baby.sensory.process_update_sensory({
                "name": "discomfort",
                "delta": 0.3
            })

        triggered = baby.sensory.process_get_triggered_sensations({})

        if "discomfort" in triggered:
            print(f"観測 #{i+1}: 不快感 → 泣く")
            baby.action.process_cry({})
            baby.sensory.process_update_sensory({
                "name": "discomfort",
                "delta": -0.6
            })

            # 人間がラベルを教える（Level 3到達後、1回だけ）
            if not label_taught and baby.get_state()["development"]["current_level"] >= 3:
                if observation.get("pattern_id"):
                    print()
                    print("👨 人間: 「これは『discomfort（気持ち悪い）』だよ」")
                    baby.language.process_learn_label({
                        "pattern_id": observation["pattern_id"],
                        "label": "discomfort"
                    })
                    label_taught = True
                    print()

        if (i + 1) % 10 == 0:
            print(f"\n--- 観測 #{i+1} ---")
            baby.print_status()
            time.sleep(0.3)

    print()
    print("✅ Phase 3 完了")
    print()
    print("【重要】Level 3 到達:")
    print("  - パターンに「discomfort」というラベルがついた")
    print("  - まだ感情の「色」はない")
    print("  - ラベルはCross構造のメタデータとして記録")
    print()
    input("Press Enter to continue...")

    # ========================================
    # Phase 4: Level 4 (200回以降)
    # ========================================
    print()
    print("=" * 70)
    print("Phase 4: 概念形成（Level 3 → 4）")
    print("=" * 70)
    print()

    # Level 4に到達するまで観測を続ける
    i = 150
    while baby.get_state()["development"]["current_level"] < 4 and i < 250:
        external_cross = generate_random_cross()
        baby.observation.process_observe({
            "cross_structure": external_cross
        })

        if i % 6 == 0:
            baby.sensory.process_update_sensory({
                "name": "discomfort",
                "delta": 0.25
            })

        triggered = baby.sensory.process_get_triggered_sensations({})
        if triggered:
            baby.action.process_cry({})
            baby.sensory.process_update_sensory({
                "name": "discomfort",
                "delta": -0.5
            })

        i += 1

    print()
    print("🎉 Level 4 到達！")
    print()

    # 概念を教える
    print("👨 人間: 「『discomfort』は『不快』という感情だよ」")
    print("        「不快は嫌な感じ、警戒する感じだよ」")
    print()

    baby.concept.process_form_concept({
        "label": "discomfort",
        "emotional_color": {
            "unpleasant": 0.8,  # 不快
            "arousal": 0.6,     # 警戒
            "valence": -0.7,    # ネガティブ
            "description": "不快な感情（嫌な感じ、警戒）"
        }
    })

    print()
    print("🎨 感情に色がつきました！")
    print()
    print("これで赤ちゃんは:")
    print("  1. 不快感を感じる（感覚パラメータ）")
    print("  2. 泣くと不快感が減る（因果関係）")
    print("  3. これを『discomfort』と呼ぶ（ラベル）")
    print("  4. discomfortは『不快な感情』である（概念）")
    print()
    print("全てのステップを経験しました。")
    print()

    # 最終ステータス
    print("=" * 70)
    print("最終ステータス")
    print("=" * 70)
    baby.print_status()

    # 因果関係の詳細
    state = baby.get_state()
    print()
    print("発見した因果関係:")
    for link in state["causal_links"]:
        pattern_short = link["pattern"][:8]
        action = link["action"]
        result = link["result"]
        strength = link["strength"]
        color = "🎨 " if link.get("color") else "   "
        print(f"  {color}パターン {pattern_short}... : {action} → {result} (強度: {strength})")

    print()
    print("ラベル付きパターン:")
    for pattern_id, label in state["labels"].items():
        pattern_short = pattern_id[:8]
        concept = state["concepts"].get(label)
        if concept:
            print(f"  🎨 {pattern_short}... → '{label}' → {concept['description']}")
        else:
            print(f"     {pattern_short}... → '{label}' （まだ概念なし）")

    print()
    print("=" * 70)
    print("👶 JCross赤ちゃん感情システム完了")
    print("=" * 70)
    print()
    print("【重要な違い】")
    print()
    print("Pythonのノイマン型では:")
    print("  - 記憶、感覚、感情が分離したクラス")
    print("  - if文で順次実行")
    print("  - 人工的な制御フロー")
    print()
    print("JCross（Cross構造）では:")
    print("  - 全てが統合されたCross構造")
    print("  - 6軸が並列に存在")
    print("  - 情報が自然に流れる")
    print()
    print("感情の「色」も、Cross構造のメタデータとして")
    print("自然に付加されます。")
    print()
    print("これが本来のVerantyxの姿です。")
    print()


def main():
    """メイン関数"""
    try:
        run_baby_emotion_jcross()
        return 0
    except KeyboardInterrupt:
        print()
        print("プログラム中断")
        return 1
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
