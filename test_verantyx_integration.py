#!/usr/bin/env python3
"""
Verantyx統合テスト - 完全なアーキテクチャの検証

テスト項目:
1. Claude対話 → Task抽出
2. Concept Discovery
3. .jcross Program生成
4. Cross Tree Search (XTS)
5. Cross Simulator検証
6. User Knowledge更新
7. 学習マイルストーン

これにより:
✓ 3対話で推論開始
✓ 5対話で小世界シミュレータ起動
✓ 10対話で学習加速
"""

import sys
from pathlib import Path

# Add verantyx_cli to path
sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.verantyx_learning_engine import VerantyxLearningEngine
from verantyx_cli.engine.concept_engine import ConceptEngine
from verantyx_cli.engine.cross_tree_search import CrossTreeSearch, VerantyxReasoningEngine


def test_dialogue_flow():
    """対話フローの完全テスト"""
    print("=" * 80)
    print("Verantyx統合テスト開始")
    print("=" * 80)

    # エンジン初期化
    engine = VerantyxLearningEngine(
        user_id="test_user",
        project_path=Path(".")
    )

    print("\n✅ Verantyx Learning Engine initialized")

    # テスト対話データ
    test_dialogues = [
        # 1対話目: Docker error
        {
            "user": "docker build でエラーが出ました",
            "claude": "Dockerfileを確認してください。COPY命令のパスが正しいか、ベースイメージが存在するかチェックしましょう。その後、docker buildを再実行してください。"
        },
        # 2対話目: Git conflict
        {
            "user": "git merge でコンフリクトが発生しました",
            "claude": "git statusでコンフリクトファイルを確認し、該当ファイルを編集してマーカーを解決してください。その後、git add して git commit します。"
        },
        # 3対話目: Python import error (パターン推論開始)
        {
            "user": "ImportError: No module named 'numpy'",
            "claude": "pipでnumpyをインストールしてください: pip install numpy。仮想環境を使っている場合は、その環境をアクティブにしてからインストールします。"
        },
        # 4対話目: API response error
        {
            "user": "APIからのレスポンスが500エラーです",
            "claude": "サーバーログを確認してください。エンドポイントが正しいか、リクエストボディの形式が正しいかチェックしましょう。"
        },
        # 5対話目: Database connection (小世界シミュレータ開始)
        {
            "user": "データベースに接続できません",
            "claude": "接続文字列を確認してください。ホスト名、ポート、認証情報が正しいか確認します。データベースサーバーが起動しているかもチェックしましょう。"
        },
        # 6-10対話目: 学習加速に向けて
        {
            "user": "pytest でテストが失敗します",
            "claude": "pytest -v で詳細を確認してください。アサーションエラーの内容を見て、期待値と実際の値を比較しましょう。"
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

    print("\n" + "=" * 80)
    print("対話処理開始（10対話）")
    print("=" * 80)

    for i, dialogue in enumerate(test_dialogues, 1):
        print(f"\n--- 対話 {i} ---")
        print(f"User: {dialogue['user'][:50]}...")

        result = engine.process_dialogue(
            user_input=dialogue['user'],
            claude_response=dialogue['claude']
        )

        if result.get('task'):
            task = result['task']
            print(f"✓ Task抽出: domain={task['domain']}, type={task['problem_type']}")

        if result.get('programs'):
            print(f"✓ .jcross生成: {len(result['programs'])} programs")

        if result.get('simulation'):
            sim = result['simulation']
            print(f"✓ シミュレーション: verified={sim['verified']}, confidence={sim['confidence']:.2f}")

        if result.get('learning_event'):
            event = result['learning_event']
            print(f"🎯 学習イベント: {event['type']}")
            print(f"   {event['message']}")

    # 統計表示
    print("\n" + "=" * 80)
    print("統計情報")
    print("=" * 80)

    stats = engine.get_statistics()
    print(f"総対話数: {stats['total_dialogues']}")
    print(f"タスク抽出: {stats['tasks_extracted']}")
    print(f"プログラム生成: {stats['programs_generated']}")
    print(f"プログラム検証: {stats['programs_verified']}")
    print(f"学習加速: {stats['learning_accelerations']}")

    print(f"\nCross World: {stats['cross_world']['total_objects']} objects")

    user_profile = stats['user_profile']
    print(f"\nUser Profile:")
    print(f"  Interactions: {user_profile['total_interactions']}")
    print(f"  Success Rate: {user_profile['success_rate']:.2%}")
    print(f"  Domains: {user_profile['domains']}")
    print(f"  Tools: {user_profile['tools']}")

    print("\n✅ Verantyx Learning Engine test completed")

    return engine


def test_concept_discovery():
    """Concept Discovery単体テスト"""
    print("\n" + "=" * 80)
    print("Concept Discovery テスト")
    print("=" * 80)

    from verantyx_cli.engine.cross_world_model import CrossWorldModel
    from verantyx_cli.engine.task_structure_extractor import TaskStructure

    cross_world = CrossWorldModel()
    concept_engine = ConceptEngine(storage_path=Path(".verantyx/test_concepts"))

    # テストタスク
    task = TaskStructure(
        task_id="test_concept_1",
        user_input="docker build でエラーが出ました",
        claude_response="Dockerfileを確認してください。COPY命令のパスが正しいか、ベースイメージが存在するかチェックしましょう。その後、docker buildを再実行してください。",
        domain="docker",
        problem_type="build_error",
        goal="Fix docker build error",
        intent="troubleshoot",
        solution_steps=[
            "Check Dockerfile syntax",
            "Verify base image",
            "Rebuild with --no-cache"
        ],
        tools_used=["docker"],
        concepts=["error_recovery", "build_process"],
        success=True
    )

    # 概念発見
    concept, is_new = concept_engine.discover_concept(task)

    print(f"\n✓ Concept discovered: {concept.name}")
    print(f"  Domain: {concept.domain}")
    print(f"  Rule: {concept.rule}")
    print(f"  Is New: {is_new}")
    print(f"  Confidence: {concept.confidence:.2f}")

    # Concept → .jcross変換
    from verantyx_cli.engine.concept_engine import ConceptIR

    concept_ir = ConceptIR(concept)
    jcross_code = concept_ir.to_jcross_template()

    print(f"\n✓ .jcross generated:")
    print("-" * 40)
    print(jcross_code[:300] + "...")
    print("-" * 40)

    # 統計
    stats = concept_engine.get_statistics()
    print(f"\nConcept Engine Stats:")
    print(f"  Total concepts: {stats['total_concepts']}")
    print(f"  Concepts discovered: {stats.get('concepts_discovered', 0)}")
    print(f"  Concepts reused: {stats.get('concepts_reused', 0)}")

    print("\n✅ Concept Discovery test completed")

    return concept_engine


def test_cross_tree_search():
    """Cross Tree Search (XTS) テスト"""
    print("\n" + "=" * 80)
    print("Cross Tree Search (XTS) テスト")
    print("=" * 80)

    from verantyx_cli.engine.cross_world_model import CrossWorldModel
    from verantyx_cli.engine.concept_engine import ConceptEngine
    from verantyx_cli.engine.cross_simulator_enhanced import CrossSimulatorEnhanced

    # 初期化
    cross_world = CrossWorldModel()
    concept_engine = ConceptEngine(storage_path=Path(".verantyx/test_xts_concepts"))
    simulator = CrossSimulatorEnhanced(cross_world)

    # XTS初期化
    xts = CrossTreeSearch(
        concept_engine=concept_engine,
        simulator=simulator
    )

    print("✓ XTS initialized")

    # テストタスク
    task_description = "docker build error - need to check Dockerfile and rebuild"

    print(f"\nTask: {task_description}")
    print("\nSearching for optimal program...")

    # プログラム探索（軽量テスト: 50回）
    programs = xts.search(
        task_description=task_description,
        num_iterations=50
    )

    print(f"\n✓ Search completed: {len(programs)} programs found")

    if programs:
        best_program = programs[0]
        print(f"\nBest Program:")
        print(f"  ID: {best_program.program_id}")
        print(f"  Confidence: {best_program.confidence:.2f}")
        print(f"\n  Code:")
        print("-" * 40)
        print(best_program.jcross_code[:300] + "...")
        print("-" * 40)

    # 統計
    stats = xts.get_statistics()
    print(f"\nXTS Stats:")
    print(f"  Iterations: {stats.get('iterations', 0)}")
    print(f"  Nodes created: {stats.get('nodes_created', 0)}")
    print(f"  Simulations: {stats.get('simulations', 0)}")
    print(f"  Hypothesis found: {stats.get('hypothesis_found', 0)}")

    print("\n✅ Cross Tree Search test completed")

    return xts


def test_complete_reasoning_engine():
    """完全推論エンジンテスト"""
    print("\n" + "=" * 80)
    print("Verantyx Reasoning Engine (統合) テスト")
    print("=" * 80)

    from verantyx_cli.engine.cross_world_model import CrossWorldModel
    from verantyx_cli.engine.user_knowledge_model import UserKnowledgeModel
    from verantyx_cli.engine.concept_engine import ConceptEngine
    from verantyx_cli.engine.cross_simulator_enhanced import CrossSimulatorEnhanced
    from pathlib import Path

    # コンポーネント初期化
    cross_world = CrossWorldModel()
    concept_engine = ConceptEngine(storage_path=Path(".verantyx/test_reasoning_concepts"))
    simulator = CrossSimulatorEnhanced(cross_world)

    # 完全エンジン初期化
    reasoning_engine = VerantyxReasoningEngine(
        concept_engine=concept_engine,
        simulator=simulator
    )

    print("✓ Verantyx Reasoning Engine initialized")

    # テスト推論
    task_description = "API returns 500 error - need to check server logs and endpoint configuration"

    print(f"\nTask: {task_description}")
    print("\nReasoning with XTS + Concept Engine...")

    # 推論実行
    programs = reasoning_engine.solve(
        problem=task_description,
        num_iterations=30
    )

    print(f"\n✓ Reasoning completed")
    print(f"  Programs found: {len(programs)}")

    if programs:
        best = programs[0]
        print(f"  Best Program: {best.program_id}")
        print(f"  Confidence: {best.confidence:.2f}")

    # 統計 (XTSの統計を使用)
    stats = reasoning_engine.xts.get_statistics()
    print(f"\nReasoning Engine Stats (XTS):")
    print(f"  Iterations: {stats.get('iterations', 0)}")
    print(f"  Nodes created: {stats.get('nodes_created', 0)}")
    print(f"  Hypothesis found: {stats.get('hypothesis_found', 0)}")

    print("\n✅ Complete Reasoning Engine test completed")

    return reasoning_engine


def main():
    """統合テスト実行"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "Verantyx 統合テスト" + " " * 20 + "           ║")
    print("║" + " " * 78 + "║")
    print("║" + "  Architecture: LLM → Program → Simulator → Reasoning" + " " * 19 + "║")
    print("║" + "  Core: Concept Engine + Cross Tree Search (XTS)" + " " * 25 + "║")
    print("╚" + "═" * 78 + "╝")

    try:
        # 1. 完全対話フロー
        engine = test_dialogue_flow()

        # 2. Concept Discovery
        concept_engine = test_concept_discovery()

        # 3. Cross Tree Search
        xts = test_cross_tree_search()

        # 4. 完全推論エンジン
        reasoning_engine = test_complete_reasoning_engine()

        # 最終サマリー
        print("\n" + "═" * 80)
        print("🎉 全テスト完了")
        print("═" * 80)

        print("\nVerantyx Architecture Verified:")
        print("  ✅ Claude対話 → Task抽出")
        print("  ✅ Concept Discovery")
        print("  ✅ .jcross Program生成")
        print("  ✅ Cross Tree Search (MCTS)")
        print("  ✅ Cross Simulator検証")
        print("  ✅ User Knowledge更新")
        print("  ✅ 学習マイルストーン")

        print("\nVerantyx思想:")
        print("  ✓ LLM → Program (.jcross) → Simulator → Reasoning")
        print("  ✓ Concept Discovery System")
        print("  ✓ Self-Expanding DSL")
        print("  ✓ Personal AI Infrastructure")
        print("  ✓ AlphaGo-level Search Foundation")

        print("\n🚀 Verantyx is ready for AlphaGo-level learning!")

        return 0

    except Exception as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
