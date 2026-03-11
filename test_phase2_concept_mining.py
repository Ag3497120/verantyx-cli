#!/usr/bin/env python3
"""
Phase 2テスト: Concept Mining

Claudeログから概念を実際に抽出する
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.jcross_vm_complete import JCrossVM
from verantyx_cli.engine.concept_mining_processors import register_to_vm


def test_concept_mining():
    """Concept Miningテスト"""
    print("=" * 80)
    print("Phase 2: Concept Mining テスト")
    print("=" * 80)

    # VM初期化
    vm = JCrossVM(storage_path=Path(".verantyx/phase2"))

    # Concept Miningプロセッサを登録
    register_to_vm(vm)

    # concept_mining.jcrossを読み込み
    jcross_file = Path("verantyx_cli/engine/concept_mining.jcross")
    with open(jcross_file, 'r', encoding='utf-8') as f:
        program = f.read()

    vm.load_program(program)

    print(f"✓ Program loaded: {len(vm.labels)} labels")
    print(f"  Labels: {list(vm.labels.keys())}")

    # テストデータ: Claude対話ログ
    test_dialogues = [
        {
            "user": "docker build でエラーが出ました",
            "claude": "Dockerfileを確認してください。まず、COPY命令のパスが正しいかチェックしましょう。次に、ベースイメージが存在するか確認します。最後に、docker buildを再実行してください。"
        },
        {
            "user": "git merge でコンフリクトが発生しました",
            "claude": "git statusでコンフリクトファイルを確認してください。該当ファイルを編集してマーカーを解決します。その後、git add して git commit してください。"
        },
        {
            "user": "ImportError: No module named 'numpy'",
            "claude": "pipでnumpyをインストールしてください: pip install numpy。仮想環境を使っている場合は、その環境をアクティブにしてからインストールします。"
        }
    ]

    print("\n" + "=" * 80)
    print("概念抽出開始")
    print("=" * 80)

    concepts_extracted = []

    for i, dialogue in enumerate(test_dialogues, 1):
        print(f"\n--- 対話 {i} ---")
        print(f"User: {dialogue['user'][:50]}...")
        print(f"Claude: {dialogue['claude'][:60]}...")

        try:
            # concept_mining_from_log を実行
            concept_id = vm.execute_label(
                "concept_mining_from_log",
                dialogue['user'],
                dialogue['claude']
            )

            print(f"✓ Concept extracted: {concept_id}")

            # Cross空間から概念データを取得
            concept_data = vm.cross_space.retrieve(concept_id)
            if concept_data:
                print(f"  Name: {concept_data.get('name', 'N/A')}")
                print(f"  Rule: {concept_data.get('rule', 'N/A')}")
                print(f"  Domain: {concept_data.get('domain', 'N/A')}")

            concepts_extracted.append(concept_id)

        except Exception as e:
            print(f"❌ Error: {e}")

    # 統計表示
    print("\n" + "=" * 80)
    print("抽出結果")
    print("=" * 80)

    print(f"概念抽出数: {len(concepts_extracted)}")
    print(f"Cross空間オブジェクト数: {len(vm.cross_space.objects)}")

    # Cross空間の内容を表示
    print("\nCross空間:")
    for key, obj in vm.cross_space.objects.items():
        print(f"  {key}: {str(obj['value'])[:80]}...")

    # 状態保存
    vm.save_state()
    print(f"\n✓ State saved to {vm.storage_path}")

    # 成功判定
    if len(concepts_extracted) >= 2:
        print("\n✅ Phase 2 test PASSED")
        print("  実際にClaudeログから概念を抽出できました！")
        return 0
    else:
        print("\n⚠️  Phase 2 test PARTIAL")
        print(f"  抽出数が少ない: {len(concepts_extracted)}/3")
        return 1


if __name__ == "__main__":
    exit(test_concept_mining())
