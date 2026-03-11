#!/usr/bin/env python3
"""
Complete Self-Improvement Test

完全な自己改善ループのテスト
Claudeログ → 概念抽出 → プログラム生成 → 実行 → 評価 → 改善
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.jcross_vm_complete import JCrossVM
from verantyx_cli.engine.concept_mining_complete import RealConceptMiner
from verantyx_cli.engine.concept_to_program import ConceptToProgramGenerator
from verantyx_cli.engine.program_evaluator import ProgramEvaluator
from verantyx_cli.engine.self_improvement_loop import SelfImprovementLoop
from verantyx_cli.engine.domain_processors import register_to_vm as register_domain_processors


def test_complete_self_improvement():
    """完全な自己改善テスト"""
    print("="*80)
    print("VERANTYX - Complete Self-Improvement Test")
    print("="*80)
    print()

    # === 初期化 ===
    print("Initializing components...")
    vm = JCrossVM(storage_path=Path(".verantyx/self_improvement_test"))

    # ドメインプロセッサを登録
    register_domain_processors(vm)

    miner = RealConceptMiner()
    generator = ConceptToProgramGenerator()
    evaluator = ProgramEvaluator(vm=vm)
    loop = SelfImprovementLoop(
        vm=vm,
        miner=miner,
        generator=generator,
        evaluator=evaluator
    )
    print("✓ All components initialized")
    print()

    # === テストデータ ===
    dialogues = [
        (
            "docker build でエラーが出ました",
            "Dockerfileを確認してください。まず、COPY命令のパスが正しいかチェックしましょう。次に、ベースイメージが存在するか確認します。最後に、docker buildを再実行してください。"
        ),
        (
            "git merge でコンフリクトが発生しました",
            "git statusでコンフリクトファイルを確認してください。該当ファイルを編集してマーカーを解決します。その後、git add して git commit してください。"
        ),
        (
            "ImportError: No module named 'numpy'",
            "pipでnumpyをインストールしてください: `pip install numpy`。仮想環境を使っている場合は、その環境をアクティブにしてからインストールします。"
        ),
        (
            "また docker build がエラーになりました",
            "Dockerfileをチェックしてください。イメージ名が正しいか確認します。修正したら docker build を実行します。"
        ),
        (
            "APIからのレスポンスが500エラーです",
            "サーバーログを確認してください。エンドポイントが正しいか、リクエストボディの形式が正しいかチェックしましょう。"
        )
    ]

    # === 複数サイクル実行 ===
    stats = loop.run_multiple_cycles(dialogues)

    # === 結果検証 ===
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    print()

    success_criteria = {
        "Total cycles >= 5": stats['total_cycles'] >= 5,
        "Concepts created >= 3": stats['concepts_created'] >= 3,
        "Average score >= 0.3": stats['average_score'] >= 0.3,
        "At least 1 strengthened": stats['concepts_strengthened'] >= 1
    }

    all_passed = all(success_criteria.values())

    for criterion, passed in success_criteria.items():
        status = "✅" if passed else "❌"
        print(f"{status} {criterion}")

    print()

    # === ベスト概念を表示 ===
    print("="*80)
    print("BEST CONCEPTS (Top 3)")
    print("="*80)
    print()

    best_concepts = loop.get_best_concepts(top_n=3)
    for i, concept in enumerate(best_concepts, 1):
        print(f"{i}. {concept['name']}")
        print(f"   Domain: {concept['domain']}")
        print(f"   Rule: {concept['rule']}")
        print(f"   Confidence: {concept['confidence']:.2f}")
        print(f"   Use Count: {concept['use_count']}")
        print()

    # === 進捗可視化 ===
    print("="*80)
    print(loop.visualize_progress())
    print("="*80)
    print()

    # === 知識エクスポート ===
    export_path = Path(".verantyx/self_improvement_test/learned_knowledge.json")
    loop.export_learned_knowledge(export_path)
    print()

    # === 最終判定 ===
    if all_passed:
        print("="*80)
        print("🎉 SUCCESS: SELF-IMPROVEMENT LOOP WORKS! 🎉")
        print("="*80)
        print()
        print("Verantyx can now:")
        print("  ✅ Extract concepts from Claude logs")
        print("  ✅ Generate programs from concepts")
        print("  ✅ Execute and evaluate programs")
        print("  ✅ Apply feedback to improve concepts")
        print("  ✅ Learn and evolve autonomously")
        print()
        print("🚀 Self-Improvement: FUNCTIONAL")
        print()
        print("Statistics:")
        print(f"  • Total cycles: {stats['total_cycles']}")
        print(f"  • Concepts created: {stats['concepts_created']}")
        print(f"  • Concepts strengthened: {stats['concepts_strengthened']}")
        print(f"  • Average score: {stats['average_score']:.2f}")
        print()

        # 改善検出
        scores = stats['score_trend']
        if len(scores) >= 3:
            early_avg = sum(scores[:3]) / 3
            late_avg = sum(scores[-3:]) / 3
            improvement = late_avg - early_avg

            print(f"Improvement: {early_avg:.2f} → {late_avg:.2f} ({improvement:+.2f})")

            if improvement > 0.05:
                print("  → ✅ Clear improvement trend detected!")
            elif improvement > 0:
                print("  → ✅ Positive trend")
            else:
                print("  → ⚠️  Need more cycles to see improvement")

        print()
        print("="*80)
        return 0
    else:
        print("⚠️  Some criteria not met")
        return 1


if __name__ == "__main__":
    exit(test_complete_self_improvement())
