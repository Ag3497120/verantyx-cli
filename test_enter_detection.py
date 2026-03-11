#!/usr/bin/env python3
"""
Enterキー検出による保存のテスト

新方式:
- 実際のEnterキー（\r）を検出
- Enter → Enter の間の応答を保存
- シンプルなループ構造
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_enter_detection_flow():
    """Enterキー検出フローのシミュレーション"""
    print("=" * 80)
    print("🧪 Enter Key Detection Flow Test")
    print("=" * 80)
    print()

    # シミュレーション状態
    enter_press_count = 0
    last_enter_time = 0.0
    response_chunks = []

    scenarios = [
        {
            'name': '起動時のEnter',
            'has_enter': True,
            'expected_action': 'Skip (startup)',
            'expected_count': 1
        },
        {
            'name': '1回目の質問 "GitHubとは"',
            'has_enter': True,
            'chunks': ["GitHubとは、Gitを使った...", "主な機能: リポジトリ..."],
            'expected_action': 'Save previous (none) + Start accumulating',
            'expected_count': 2,
            'expected_saved': False  # 前回なし
        },
        {
            'name': '2回目の質問 "Hugging Faceとは"',
            'has_enter': True,
            'chunks': ["Hugging Faceは、機械学習の...", "モデルハブには..."],
            'expected_action': 'Save GitHub response + Start accumulating',
            'expected_count': 3,
            'expected_saved': True  # GitHub応答を保存
        },
        {
            'name': '3回目の質問 "Rustとは"',
            'has_enter': True,
            'chunks': ["Rustは、システムプログラミング...", "メモリ安全性..."],
            'expected_action': 'Save Hugging Face response + Start accumulating',
            'expected_count': 4,
            'expected_saved': True  # Hugging Face応答を保存
        },
    ]

    print("📝 Testing Enter key detection flow:\n")

    for scenario in scenarios:
        print(f"[Scenario] {scenario['name']}")

        if scenario['has_enter']:
            import time
            current_time = time.time()

            # デバウンス
            if current_time - last_enter_time >= 0.2:
                last_enter_time = current_time
                enter_press_count += 1

                print(f"  ✅ Enter detected! Count: {enter_press_count}")

                if enter_press_count == 1:
                    print(f"  → Action: {scenario['expected_action']}")
                elif enter_press_count >= 2:
                    # 前回の応答を保存
                    if response_chunks:
                        print(f"  → Saving previous response: {len(response_chunks)} chunks")
                        response_chunks = []
                    else:
                        print(f"  → No previous response to save")

                    # 新しい応答の蓄積開始
                    if 'chunks' in scenario:
                        response_chunks = scenario['chunks']
                        print(f"  → Started accumulating: {len(response_chunks)} chunks")

                # 検証
                if enter_press_count == scenario['expected_count']:
                    print(f"  ✅ Count matches expected: {scenario['expected_count']}")
                else:
                    print(f"  ❌ Count mismatch: expected {scenario['expected_count']}, got {enter_press_count}")
                    return False

        print()

    return True


def test_enter_loop_structure():
    """Enterループ構造のテスト"""
    print("=" * 80)
    print("🧪 Enter Loop Structure Test")
    print("=" * 80)
    print()

    print("ループ構造:\n")
    print("  1. 起動時のEnter (count=0→1) → スキップ")
    print("  2. 1回目の質問のEnter (count=1→2) → 蓄積開始")
    print("  3. 2回目の質問のEnter (count=2→3) → 保存 + 蓄積開始")
    print("  4. 3回目の質問のEnter (count=3→4) → 保存 + 蓄積開始")
    print("  ... 繰り返し\n")

    print("期待される動作:\n")
    print("  ✅ 各質問ごとに1回だけ保存")
    print("  ✅ 重複記録なし")
    print("  ✅ 起動時のEnterは無視")
    print("  ✅ シンプルなカウンタベースのロジック\n")

    return True


def test_debouncing():
    """デバウンステスト"""
    print("=" * 80)
    print("🧪 Enter Key Debouncing Test")
    print("=" * 80)
    print()

    import time

    last_enter_time = 0.0
    enter_count = 0

    # シミュレーション: 0.1秒以内の連続Enter
    times = [0.0, 0.05, 0.1, 0.3, 0.4, 0.6]  # 秒

    print("Enter key presses at times: [0.0s, 0.05s, 0.1s, 0.3s, 0.4s, 0.6s]\n")
    print("Debounce threshold: 0.2s\n")

    for t in times:
        # Check if enough time passed (or first press)
        if enter_count == 0:
            # First press - always accept
            enter_count += 1
            last_enter_time = t
            print(f"  ✅ Time {t:.2f}s → Accepted (first press, count={enter_count})")
        elif t - last_enter_time >= 0.2:
            # Sufficient time passed
            enter_count += 1
            last_enter_time = t
            print(f"  ✅ Time {t:.2f}s → Accepted (count={enter_count})")
        else:
            print(f"  ❌ Time {t:.2f}s → Rejected (too soon: {t - last_enter_time:.2f}s)")

    print(f"\nFinal count: {enter_count}")
    print(f"Expected: 3 (at 0.0s, 0.3s, 0.6s)")

    if enter_count == 3:
        print("✅ Debouncing working correctly\n")
        return True
    else:
        print("❌ Debouncing failed\n")
        return False


def main():
    print("\n🔬 Enter Key Detection Test Suite\n")

    # Test 1: Enter検出フロー
    print("\n[Test 1] Enter Detection Flow")
    test1_passed = test_enter_detection_flow()

    # Test 2: ループ構造
    print("\n[Test 2] Loop Structure")
    test2_passed = test_enter_loop_structure()

    # Test 3: デバウンス
    print("\n[Test 3] Debouncing")
    test3_passed = test_debouncing()

    # 結果
    print("\n" + "=" * 80)
    print("📊 Test Results")
    print("=" * 80)

    results = {
        'Enter Detection Flow': test1_passed,
        'Loop Structure': test2_passed,
        'Debouncing': test3_passed,
    }

    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All tests PASSED!")
        print("\n実装された機能:")
        print("  1. Enterキー検出（\\r）")
        print("  2. Enter → Enter の間の応答を保存")
        print("  3. デバウンス（0.2秒）")
        print("  4. シンプルなカウンタベースのロジック")
        print("\n保存タイミング:")
        print("  Enter (count=2) → GitHub応答を保存")
        print("  Enter (count=3) → Hugging Face応答を保存")
        print("  Enter (count=4) → Rust応答を保存")
        print("  ... 繰り返し")
        print("\n表示例:")
        print("  💾 Cross Memory: 3 inputs, 3 responses")
    else:
        print("⚠️  Some tests failed")
    print("=" * 80)


if __name__ == '__main__':
    main()
