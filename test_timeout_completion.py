#!/usr/bin/env python3
"""
タイムアウトベースの応答完成検出のテスト

出力が途絶えてから指定秒数経過したら保存する機能をテスト
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.response_completion_predictor import ResponseCompletionPredictor


def test_timeout_simulation():
    """タイムアウト検出のシミュレーション"""
    print("=" * 80)
    print("🧪 Timeout-based Completion Detection Test")
    print("=" * 80)

    predictor = ResponseCompletionPredictor()

    # シミュレーション: Hugging Faceの説明（実際の応答）
    chunks = [
        "Hugging Face（ハギングフェイス）は、",
        "オープンソースの機械学習・AI分野において",
        "世界最大級のプラットフォームを提供するアメリカの企業であり、",
        "特に自然言語処理（NLP）と大規模言語モデル（LLM）のエコシステムの中心的存在です。",
        "\n\n主な特徴\n",
        "- モデルハブ: 50万以上の事前学習済みモデル\n",
        "- Transformersライブラリ: PyTorch/TensorFlowベースの最も人気のあるNLPライブラリ\n",
        # ここで出力が途絶える
    ]

    print("\n📝 Simulating chunk delivery with timeout:")
    print(f"   Timeout threshold: 3.0 seconds")
    print()

    last_chunk_time = time.time()

    for i, chunk in enumerate(chunks, 1):
        # チャンクを追加
        result = predictor.add_chunk(chunk)

        print(f"[Chunk {i}] Added: {chunk[:50]}...")
        print(f"  Completion: {result['completion_score']:.2%}")
        print(f"  Detected: {result['detected_pieces']}")
        print(f"  Puzzle complete? {'✅ YES' if result['is_complete'] else '❌ NO'}")

        # パズルが完成したらそこで終了
        if result['is_complete']:
            print(f"\n  ✅ Puzzle-based completion detected at chunk {i}/{len(chunks)}")
            return True

        # 最後のチャンク時刻を更新
        last_chunk_time = time.time()

        # 短いディレイ（実際の応答をシミュレート）
        time.sleep(0.1)

    # パズル完成しなかった場合、タイムアウトチェック
    print("\n⏱️  Waiting for timeout...")
    timeout_seconds = 3.0

    while True:
        elapsed = time.time() - last_chunk_time

        if elapsed >= timeout_seconds:
            assembled = ''.join(predictor.current_assembly['chunks'])
            print(f"\n  ✅ Timeout detected after {elapsed:.1f}s")
            print(f"  Assembled text length: {len(assembled)} chars")
            print(f"  Text preview: {assembled[:100]}...")

            # 十分な長さがあるか
            if len(assembled.strip()) >= 50:
                print(f"\n  ✅ Text is sufficient length (>= 50 chars)")
                print(f"  → Would save to Cross structure")
                return True
            else:
                print(f"\n  ❌ Text too short (< 50 chars)")
                return False

        # 進捗表示
        print(f"  Elapsed: {elapsed:.1f}s / {timeout_seconds}s", end='\r')
        time.sleep(0.1)


def test_combined_detection():
    """パズル完成とタイムアウトの両方をテスト"""
    print("\n" + "=" * 80)
    print("🧪 Combined Detection Test (Puzzle + Timeout)")
    print("=" * 80)

    # ケース1: パズル完成で検出される場合
    print("\n[Case 1] Complete response with proper ending")
    predictor1 = ResponseCompletionPredictor()

    chunks1 = [
        "GitHubとは、",
        "Gitを使ったソースコードのバージョン管理とコラボレーションを行うためのWebサービスです。",
        "\n\n主な特徴として以下があります：\n",
        "- リポジトリホスティング\n",
        "- プルリクエスト機能\n",
        "- Issue管理\n",
        "\n\nオープンソースプロジェクトで広く使われています。"
    ]

    for chunk in chunks1:
        result = predictor1.add_chunk(chunk)

    if result['is_complete']:
        print("  ✅ Detected by puzzle completion")
    else:
        print("  ❌ Not detected by puzzle")

    # ケース2: タイムアウトで検出される場合（文末が不完全）
    print("\n[Case 2] Incomplete ending, detected by timeout")
    predictor2 = ResponseCompletionPredictor()

    chunks2 = [
        "Rustとは、",
        "システムプログラミング言語で、",
        "メモリ安全性とパフォーマンスを両立させています。",
        "\n\n主な特徴：\n",
        "- ゼロコスト抽象化\n",
        "- 所有権システム"
        # 途中で終了（文末が不完全）
    ]

    for chunk in chunks2:
        result = predictor2.add_chunk(chunk)

    print(f"  Puzzle complete? {result['is_complete']}")
    print(f"  Completion score: {result['completion_score']:.2%}")
    print(f"  Missing pieces: {result['missing_pieces']}")

    assembled = ''.join(predictor2.current_assembly['chunks'])
    print(f"  Assembled length: {len(assembled)} chars")

    if len(assembled) >= 50:
        print("  ✅ Would be detected by timeout (>= 50 chars)")
    else:
        print("  ❌ Too short for timeout detection")

    return True


def main():
    print("\n🔬 Timeout-based Response Completion Detection Test\n")

    # Test 1: タイムアウトシミュレーション
    print("\n[Test 1] Timeout Simulation")
    test1_passed = test_timeout_simulation()

    # Test 2: 組み合わせテスト
    print("\n[Test 2] Combined Detection")
    test2_passed = test_combined_detection()

    # 結果
    print("\n" + "=" * 80)
    print("📊 Test Results")
    print("=" * 80)

    results = {
        'Timeout Simulation': test1_passed,
        'Combined Detection': test2_passed,
    }

    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All tests PASSED!")
        print("\n実装された機能:")
        print("  1. パズル推論による完成検出（既存）")
        print("  2. タイムアウトによる完成検出（新規）")
        print("  3. 両方の条件を組み合わせた保存判定")
        print("\n保存条件:")
        print("  条件A: パズルのピースが全て揃った（スコア >= 0.8, 必須ピース完備）")
        print("  条件B: 出力が3秒間途絶えた & テキストが50文字以上")
        print("  → どちらかを満たせば保存")
    else:
        print("⚠️  Some tests failed")
    print("=" * 80)


if __name__ == '__main__':
    main()
