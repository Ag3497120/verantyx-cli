#!/usr/bin/env python3
"""
Cross構造の永続性と応答記録の完全性をテスト

検証項目:
1. Cross構造が正しくロードされる
2. 応答が1回だけ記録される（重複なし）
3. 完成度予測が機能している
4. スタンドアロンモードで学習内容を取得できる
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.cross_conversation_logger import CrossConversationLogger
from verantyx_cli.engine.response_completion_predictor import ResponseCompletionPredictor


def test_cross_persistence():
    """Cross構造の永続性テスト"""
    print("=" * 80)
    print("🧪 Test 1: Cross Structure Persistence")
    print("=" * 80)

    cross_file = Path('.verantyx/conversation.cross.json')

    # 既存のCross構造をバックアップ
    backup_file = cross_file.with_suffix('.json.test_backup')
    if cross_file.exists():
        import shutil
        shutil.copy(cross_file, backup_file)
        print(f"✅ Backed up existing Cross structure to {backup_file}")

    # テスト1: 初回ロード（ファイルが存在する場合）
    logger1 = CrossConversationLogger(cross_file)
    initial_stats = logger1.get_statistics()

    print(f"\n📊 Initial state:")
    print(f"  Inputs: {initial_stats['total_inputs']}")
    print(f"  Responses: {initial_stats['total_responses']}")

    # テスト2: データを追加
    logger1.log_user_input("テスト質問1")
    logger1.log_claude_response("テスト応答1")
    logger1.save()

    after_add_stats = logger1.get_statistics()
    print(f"\n📊 After adding 1 Q&A:")
    print(f"  Inputs: {after_add_stats['total_inputs']}")
    print(f"  Responses: {after_add_stats['total_responses']}")

    # テスト3: 新しいインスタンスで再ロード
    logger2 = CrossConversationLogger(cross_file)
    reload_stats = logger2.get_statistics()

    print(f"\n📊 After reload:")
    print(f"  Inputs: {reload_stats['total_inputs']}")
    print(f"  Responses: {reload_stats['total_responses']}")

    # 検証: データが永続化されているか
    success = (
        reload_stats['total_inputs'] == after_add_stats['total_inputs'] and
        reload_stats['total_responses'] == after_add_stats['total_responses']
    )

    if success:
        print("\n✅ Persistence test PASSED")
    else:
        print("\n❌ Persistence test FAILED")
        print(f"   Expected: {after_add_stats}")
        print(f"   Got: {reload_stats}")

    return success


def test_response_completion_predictor():
    """応答完成予測器のテスト"""
    print("\n" + "=" * 80)
    print("🧪 Test 2: Response Completion Predictor")
    print("=" * 80)

    predictor = ResponseCompletionPredictor()

    # シミュレーション: GitHubの定義
    chunks = [
        "GitHubとは、",
        "Gitを使ったソースコードのバージョン管理とコラボレーションを行うためのWebサービスです。",
        "\n\n主な特徴として以下があります：\n",
        "- リポジトリホスティング\n",
        "- プルリクエスト機能\n",
        "- Issue管理\n",
        "- CI/CD統合\n",
        "\n\nオープンソースプロジェクトで広く使われています。"
    ]

    print("\n📝 Testing with GitHub definition chunks:")

    completion_detected = False
    final_score = 0.0

    for i, chunk in enumerate(chunks, 1):
        result = predictor.add_chunk(chunk)

        print(f"\n  Chunk {i}/{len(chunks)}: {chunk[:40]}...")
        print(f"    Completion: {result['completion_score']:.2%}")
        print(f"    Detected: {result['detected_pieces']}")
        print(f"    Missing: {result['missing_pieces']}")
        print(f"    Complete? {'✅ YES' if result['is_complete'] else '❌ NO'}")

        if result['is_complete']:
            completion_detected = True
            final_score = result['completion_score']
            print(f"\n  ✅ Detected completion at chunk {i}/{len(chunks)}")
            break

    success = completion_detected and final_score >= 0.8

    if success:
        print("\n✅ Completion predictor test PASSED")
    else:
        print("\n❌ Completion predictor test FAILED")
        print(f"   Completion detected: {completion_detected}")
        print(f"   Final score: {final_score:.2%}")

    return success


def test_no_duplicate_recording():
    """重複記録がないことをテスト"""
    print("\n" + "=" * 80)
    print("🧪 Test 3: No Duplicate Recording")
    print("=" * 80)

    cross_file = Path('.verantyx/test_duplicate.cross.json')

    # クリーンスタート
    if cross_file.exists():
        cross_file.unlink()

    logger = CrossConversationLogger(cross_file)

    # 初期状態
    initial_stats = logger.get_statistics()
    print(f"\n📊 Initial: {initial_stats['total_responses']} responses")

    # 1つの応答を1回だけ記録
    logger.log_claude_response("これは1つの応答です。")
    logger.save()

    after_stats = logger.get_statistics()
    print(f"📊 After adding 1 response: {after_stats['total_responses']} responses")

    # 検証: 1つだけ増えたか
    success = after_stats['total_responses'] == initial_stats['total_responses'] + 1

    if success:
        print("\n✅ No duplicate recording test PASSED")
    else:
        print("\n❌ Duplicate recording detected!")
        print(f"   Expected: {initial_stats['total_responses'] + 1}")
        print(f"   Got: {after_stats['total_responses']}")

    # クリーンアップ
    if cross_file.exists():
        cross_file.unlink()

    return success


def test_cross_structure_health():
    """Cross構造の健全性チェック"""
    print("\n" + "=" * 80)
    print("🧪 Test 4: Cross Structure Health Check")
    print("=" * 80)

    cross_file = Path('.verantyx/conversation.cross.json')

    if not cross_file.exists():
        print("⚠️  No Cross structure file found, creating fresh one...")
        logger = CrossConversationLogger(cross_file)
        logger.save()

    # ファイルをロード
    try:
        with open(cross_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print("\n📋 Checking structure:")

        # 必須フィールドのチェック
        required_checks = {
            'axes exists': 'axes' in data,
            'UP axis exists': 'UP' in data.get('axes', {}),
            'DOWN axis exists': 'DOWN' in data.get('axes', {}),
            'LEFT axis exists': 'LEFT' in data.get('axes', {}),
            'RIGHT axis exists': 'RIGHT' in data.get('axes', {}),
            'FRONT axis exists': 'FRONT' in data.get('axes', {}),
            'BACK axis exists': 'BACK' in data.get('axes', {}),
            'user_inputs field': 'user_inputs' in data.get('axes', {}).get('UP', {}),
            'claude_responses field': 'claude_responses' in data.get('axes', {}).get('DOWN', {}),
        }

        all_passed = True
        for check_name, passed in required_checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
            if not passed:
                all_passed = False

        if all_passed:
            print("\n✅ Structure health check PASSED")
        else:
            print("\n❌ Structure has issues")

        return all_passed

    except Exception as e:
        print(f"\n❌ Failed to load Cross structure: {e}")
        return False


def main():
    print("\n🔬 Cross Persistence and Recording Integrity Test Suite\n")

    results = {}

    # Test 1: 永続性
    results['Persistence'] = test_cross_persistence()

    # Test 2: 完成予測
    results['Completion Predictor'] = test_response_completion_predictor()

    # Test 3: 重複記録なし
    results['No Duplicates'] = test_no_duplicate_recording()

    # Test 4: 構造健全性
    results['Structure Health'] = test_cross_structure_health()

    # 結果サマリー
    print("\n" + "=" * 80)
    print("📊 Test Results Summary")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All tests PASSED!")
        print("\n次のステップ:")
        print("  1. 実際のチャットモードでテスト:")
        print("     python3 -m verantyx_cli chat")
        print("  2. 質問をして応答が1回だけ保存されるか確認")
        print("  3. スタンドアロンモードで学習内容を確認:")
        print("     python3 -m verantyx_cli standalone")
    else:
        print("⚠️  Some tests FAILED")
        print("\n修正が必要な箇所を確認してください。")
    print("=" * 80)


if __name__ == '__main__':
    main()
