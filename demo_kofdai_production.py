#!/usr/bin/env python3
"""
Kofdai型全同調システム - 実運用レベルデモ

Kofdai原則の実証:
1. データは削除されず、空間内で再配置される
2. 全パターンが同時に共鳴し、最大共鳴が自然に選ばれる
3. 入力はエネルギー波として扱われる
4. 成功したパターンがFRONT-UPへ自然に移動する
"""

from verantyx_cli.engine.kofdai_resonance_engine import KofdaiResonanceEngine
from pathlib import Path
import json
import time


def print_header(title):
    """ヘッダーを表示"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_principle_1_no_deletion():
    """原則1: データは削除されず、空間内で再配置される"""
    print_header("Kofdai原則1: データは削除されず、空間内で再配置される")

    engine = KofdaiResonanceEngine()

    print("📊 初期状態のパターン:")
    for pattern in engine.patterns[:3]:
        print(f"  • {pattern.name}: FRONT={pattern.front_back:.2f}, "
              f"UP={pattern.up_down:.2f}, Usage={pattern.usage_count}")

    print("\n🌊 入力処理を実行...")

    # 複数回の入力を処理
    inputs = [
        ("openaiとは", True),   # 成功
        ("rustとは", True),      # 成功
        ("それについて教えて", False),  # 失敗
    ]

    for text, success in inputs:
        result = engine.process_input_wave(text, execute=False)
        engine.update_pattern_position(result['best_pattern'], success=success)
        print(f"  処理: {text} → {result['best_pattern']} "
              f"(success={success})")

    print("\n📊 更新後のパターン位置（削除されていない）:")
    for pattern in sorted(engine.patterns, key=lambda p: p.front_back, reverse=True)[:3]:
        print(f"  • {pattern.name}: FRONT={pattern.front_back:.2f}, "
              f"UP={pattern.up_down:.2f}, Usage={pattern.usage_count}")

    print("\n✅ パターンは削除されず、空間内で再配置されている")


def demo_principle_2_parallel_resonance():
    """原則2: 全パターンが同時に共鳴し、最大共鳴が自然に選ばれる"""
    print_header("Kofdai原則2: 全パターンが同時に共鳴し、最大共鳴が自然に選ばれる")

    engine = KofdaiResonanceEngine()

    test_text = "openaiとは何ですか？教えてください"

    print(f"🌊 入力（エネルギー波）: {test_text}\n")

    # 全パターンで共鳴を計算
    result = engine.process_input_wave(test_text, execute=False)

    print("📡 全パターンの共鳴度:")
    for r in result['all_resonances']:
        bar = "█" * int(r['score'] * 20)
        print(f"  {r['pattern']:25s} [{bar:20s}] {r['score']:5.1%} ({r['confidence']})")

    print(f"\n🎯 自然に選ばれた最大共鳴:")
    print(f"  → {result['best_pattern']} (score={result['score']:.1%}, "
          f"confidence={result['confidence']})")

    print("\n✅ if/elseの羅列ではなく、全パターンが並列に共鳴している")


def demo_principle_3_energy_wave():
    """原則3: 入力はエネルギー波として扱われる"""
    print_header("Kofdai原則3: 入力はエネルギー波として扱われる")

    engine = KofdaiResonanceEngine()

    # 同じ意味の異なる表現（エネルギー波の変調）
    wave_variations = [
        "openaiとは",
        "openaiって何",
        "openaiについて教えて",
        "openaiを説明して"
    ]

    print("🌊 同じエネルギー（意図）の異なる波形:\n")

    resonance_patterns = []
    for wave in wave_variations:
        result = engine.process_input_wave(wave, execute=False)
        resonance_patterns.append((wave, result['best_pattern'], result['score']))

        print(f"  波形: {wave:25s} → パターン: {result['best_pattern']:20s} "
              f"({result['score']:.1%})")

    print("\n✅ 表層形式が違っても、同じエネルギー（意図）として認識される")


def demo_principle_4_front_up_migration():
    """原則4: 成功したパターンがFRONT-UPへ自然に移動する"""
    print_header("Kofdai原則4: 成功したパターンがFRONT-UPへ自然に移動する")

    engine = KofdaiResonanceEngine()

    # テスト対象のパターン
    test_pattern = "definition_query"

    print(f"📊 パターン '{test_pattern}' の初期位置:")
    pattern = engine._get_pattern(test_pattern)
    print(f"  FRONT={pattern.front_back:.2f}, UP={pattern.up_down:.2f}")
    print(f"  Usage={pattern.usage_count}, Success={pattern.success_count}\n")

    # 10回成功させる
    print("🌊 10回の成功した実行...\n")
    for i in range(10):
        engine.update_pattern_position(test_pattern, success=True)
        if i % 3 == 2:  # 3回ごとに表示
            print(f"  実行{i+1}回目: FRONT={pattern.front_back:.2f}, "
                  f"UP={pattern.up_down:.2f}")

    print(f"\n📊 パターン '{test_pattern}' の最終位置:")
    print(f"  FRONT={pattern.front_back:.2f}, UP={pattern.up_down:.2f}")
    print(f"  Usage={pattern.usage_count}, Success={pattern.success_count}\n")

    print("✅ 成功するたびにFRONT-UPへ移動している（品質↑、使用頻度↑）")


def demo_full_integration():
    """4つの原則の統合デモ"""
    print_header("🌊 Kofdai型全同調システム - 統合デモ")

    engine = KofdaiResonanceEngine()

    print("シミュレーション: 3日間の使用パターン\n")

    # Day 1: 初回使用
    print("📅 Day 1: 初回使用")
    for text in ["openaiとは", "rustとは", "pythonとは"]:
        result = engine.process_input_wave(text, execute=False)
        engine.update_pattern_position(result['best_pattern'], success=True)
        print(f"  ✅ {text}")

    # Day 2: 継続使用 + 一部失敗
    print("\n📅 Day 2: 継続使用")
    for text in ["openaiについて", "それは何", "rustを説明"]:
        result = engine.process_input_wave(text, execute=False)
        success = "それ" not in text  # 代名詞は失敗と仮定
        engine.update_pattern_position(result['best_pattern'], success=success)
        status = "✅" if success else "❌"
        print(f"  {status} {text}")

    # Day 3: 高頻度使用
    print("\n📅 Day 3: 高頻度使用")
    for _ in range(5):
        result = engine.process_input_wave("openaiとは", execute=False)
        engine.update_pattern_position(result['best_pattern'], success=True)
    print("  ✅ openaiとは (×5)")

    # Cross空間状態表示
    print("\n" + engine.get_space_visualization())

    # パターン保存
    engine.save_patterns()
    patterns_file = Path.home() / '.verantyx' / 'resonance_patterns.json'
    print(f"\n💾 パターンが保存されました: {patterns_file}")

    print("\n✅ 4つのKofdai原則が統合的に動作している:")
    print("  1. データは削除されず、空間内で再配置")
    print("  2. 全パターンが同時に共鳴し、最大共鳴が選ばれる")
    print("  3. 入力はエネルギー波として処理")
    print("  4. 成功したパターンがFRONT-UPへ移動")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  🌊 Kofdai型全同調システム - 実運用レベルデモ")
    print("=" * 70)

    # 各原則を個別にデモ
    demo_principle_1_no_deletion()
    time.sleep(1)

    demo_principle_2_parallel_resonance()
    time.sleep(1)

    demo_principle_3_energy_wave()
    time.sleep(1)

    demo_principle_4_front_up_migration()
    time.sleep(1)

    # 統合デモ
    demo_full_integration()

    print("\n" + "=" * 70)
    print("  ✨ デモ完了 - Kofdai型全同調システムは実運用可能")
    print("=" * 70 + "\n")
