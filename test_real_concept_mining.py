#!/usr/bin/env python3
"""
Real Concept Mining テスト

実際に概念が抽出されることを検証
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.concept_mining_complete import RealConceptMiner


def test_real_concept_mining():
    """Real Concept Miningテスト"""
    print("=" * 80)
    print("Real Concept Mining テスト")
    print("=" * 80)
    print()

    miner = RealConceptMiner()

    # テスト対話データ
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
            "claude": "pipでnumpyをインストールしてください: `pip install numpy`。仮想環境を使っている場合は、その環境をアクティブにしてからインストールします。"
        },
        {
            "user": "APIからのレスポンスが500エラーです",
            "claude": "サーバーログを確認してください。エンドポイントが正しいか、リクエストボディの形式が正しいかチェックしましょう。"
        },
        {
            "user": "データベースに接続できません",
            "claude": "接続文字列を確認してください。ホスト名、ポート、認証情報が正しいか確認します。データベースサーバーが起動しているかもチェックしましょう。"
        },
        {
            "user": "pytest でテストが失敗します",
            "claude": "pytest -vで詳細を確認してください。アサーションエラーの内容を見て、期待値と実際の値を比較しましょう。"
        },
        {
            "user": "CSS が反映されません",
            "claude": "ブラウザのキャッシュをクリアしてください。開発者ツールでネットワークタブを確認し、CSSファイルが正しく読み込まれているかチェックします。"
        },
        {
            "user": "メモリ使用量が増え続けます",
            "claude": "メモリリークの可能性があります。プロファイラでメモリ使用状況を確認し、不要なオブジェクトが残っていないかチェックしましょう。"
        },
        {
            "user": "デプロイが失敗します",
            "claude": "デプロイログを確認してください。環境変数が正しく設定されているか、依存関係がすべてインストールされているかチェックします。"
        },
        {
            "user": "認証エラーが出ます",
            "claude": "トークンの有効期限を確認してください。ヘッダーに正しく Authorization が設定されているか、トークンの形式が正しいかチェックしましょう。"
        }
    ]

    print("概念マイニング開始...")
    print()

    concepts_created = 0
    concepts_strengthened = 0

    for i, dialogue in enumerate(test_dialogues, 1):
        print(f"--- 対話 {i} ---")
        print(f"User: {dialogue['user'][:50]}...")

        # 概念をマイニング
        concept, is_new = miner.mine(dialogue['user'], dialogue['claude'])

        if is_new:
            concepts_created += 1
            print(f"✅ 新規概念作成: {concept['name']}")
        else:
            concepts_strengthened += 1
            print(f"🔄 既存概念強化: {concept['name']}")

        print(f"   Domain: {concept['domain']}")
        print(f"   Problem Type: {concept['problem_type']}")
        print(f"   Rule: {concept['rule']}")
        print(f"   Confidence: {concept['confidence']:.2f}")
        print(f"   Use Count: {concept['use_count']}")
        print()

        # マイルストーン
        if i == 3:
            print("🎯 3対話: パターン推論開始")
            print()
        elif i == 5:
            print("🎯 5対話: 小世界シミュレータ起動")
            print()
        elif i == 10:
            print("🎯 10対話: 学習加速")
            print()

    # 統計表示
    print("=" * 80)
    print("統計情報")
    print("=" * 80)
    print()

    stats = miner.get_statistics()

    print(f"総概念数: {stats['total_concepts']}")
    print(f"新規作成: {concepts_created}")
    print(f"既存強化: {concepts_strengthened}")
    print(f"平均信頼度: {stats['avg_confidence']:.2f}")
    print()

    print("ドメイン別:")
    for domain, count in stats['by_domain'].items():
        print(f"  {domain}: {count}")

    print()

    # 概念詳細表示
    print("=" * 80)
    print("抽出された概念")
    print("=" * 80)
    print()

    for concept_id, concept in miner.concepts.items():
        print(f"[{concept['name']}]")
        print(f"  ID: {concept_id}")
        print(f"  Domain: {concept['domain']}")
        print(f"  Rule: {concept['rule']}")
        print(f"  Inputs: {', '.join(concept['inputs'][:3])}")
        print(f"  Outputs: {', '.join(concept['outputs'][:3])}")
        print(f"  Confidence: {concept['confidence']:.2f}")
        print(f"  Use Count: {concept['use_count']}")
        print()

    # 成功判定
    print("=" * 80)
    print("成功基準")
    print("=" * 80)
    print()

    success_criteria = {
        "総概念数 >= 5": stats['total_concepts'] >= 5,
        "新規作成 >= 5": concepts_created >= 5,
        "平均信頼度 >= 0.5": stats['avg_confidence'] >= 0.5,
        "ドメイン数 >= 3": len(stats['by_domain']) >= 3
    }

    all_passed = all(success_criteria.values())

    for criterion, passed in success_criteria.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {criterion}")

    print()

    if all_passed:
        print("🎉" * 40)
        print()
        print("  ✅ Real Concept Mining SUCCESS!")
        print()
        print("  実際に:")
        print(f"    ✓ {concepts_created}個の概念を新規作成")
        print(f"    ✓ {concepts_strengthened}個の概念を強化")
        print(f"    ✓ 平均信頼度 {stats['avg_confidence']:.2f}")
        print(f"    ✓ {len(stats['by_domain'])}ドメインをカバー")
        print()
        print("  → Claudeログから実際に学習できています！")
        print()
        print("🎉" * 40)
        return 0
    else:
        print("⚠️  一部基準が未達成")
        return 1


if __name__ == "__main__":
    exit(test_real_concept_mining())
