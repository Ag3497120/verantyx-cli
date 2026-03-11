#!/usr/bin/env python3
"""
Real Log Learning Test

実際のClaudeログファイルから学習して自己改善ループを回すテスト
"""

import sys
import re
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.jcross_vm_complete import JCrossVM
from verantyx_cli.engine.concept_mining_complete import RealConceptMiner
from verantyx_cli.engine.concept_to_program import ConceptToProgramGenerator
from verantyx_cli.engine.program_evaluator import ProgramEvaluator
from verantyx_cli.engine.self_improvement_loop import SelfImprovementLoop
from verantyx_cli.engine.domain_processors import register_to_vm as register_domain_processors
from verantyx_cli.engine.cross_simulator import register_to_vm as register_cross_sim
from verantyx_cli.engine.dynamic_code_generator import register_to_vm as register_dynamic_gen
from verantyx_cli.engine.xts_puzzle_reasoning import register_to_vm as register_xts
from verantyx_cli.engine.world_model import register_to_vm as register_world_model


def parse_log_file(log_path: Path) -> List[Tuple[str, str]]:
    """
    ログファイルから対話を抽出

    フォーマット想定:
    - User: ... / Assistant: ...
    - Human: ... / Claude: ...
    - Q: ... / A: ...
    """
    print(f"\n[Parsing] {log_path.name}")

    if not log_path.exists():
        print(f"  ⚠️  File not found: {log_path}")
        return []

    content = log_path.read_text(encoding='utf-8', errors='ignore')

    dialogues = []

    # パターン1: User/Assistant
    pattern1 = re.compile(r'User[:\s]+(.+?)\s+Assistant[:\s]+(.+?)(?=User[:\s]+|$)', re.DOTALL | re.IGNORECASE)
    matches1 = pattern1.findall(content)

    # パターン2: Human/Claude
    pattern2 = re.compile(r'Human[:\s]+(.+?)\s+Claude[:\s]+(.+?)(?=Human[:\s]+|$)', re.DOTALL | re.IGNORECASE)
    matches2 = pattern2.findall(content)

    # パターン3: Q/A
    pattern3 = re.compile(r'Q[:\s]+(.+?)\s+A[:\s]+(.+?)(?=Q[:\s]+|$)', re.DOTALL | re.IGNORECASE)
    matches3 = pattern3.findall(content)

    all_matches = matches1 + matches2 + matches3

    for user_text, assistant_text in all_matches:
        # クリーンアップ
        user_clean = user_text.strip()[:500]  # 最初の500文字
        assistant_clean = assistant_text.strip()[:1000]  # 最初の1000文字

        if len(user_clean) > 10 and len(assistant_clean) > 10:
            dialogues.append((user_clean, assistant_clean))

    print(f"  ✅ Extracted {len(dialogues)} dialogues")

    return dialogues


def test_real_log_learning(log_files: List[Path], max_dialogues_per_file: int = 10):
    """実際のログファイルから学習テスト"""
    print("="*80)
    print("REAL LOG LEARNING TEST")
    print("="*80)
    print()

    # === 初期化 ===
    print("[Phase 1] Initializing Verantyx System...")
    print()

    vm = JCrossVM(storage_path=Path(".verantyx/real_log_learning"))
    register_domain_processors(vm)

    miner = RealConceptMiner()
    generator = ConceptToProgramGenerator()
    evaluator = ProgramEvaluator(vm=vm)

    cross_sim = register_cross_sim(vm)
    dynamic_gen = register_dynamic_gen(vm, cross_simulator=cross_sim)
    xts = register_xts(vm, cross_simulator=cross_sim, dynamic_generator=dynamic_gen, evaluator=evaluator)
    world_model = register_world_model(vm)

    loop = SelfImprovementLoop(
        vm=vm,
        miner=miner,
        generator=generator,
        evaluator=evaluator
    )

    print("✓ Verantyx initialized")
    print()

    # === ログファイルから対話を抽出 ===
    print("="*80)
    print("[Phase 2] Parsing Log Files")
    print("="*80)

    all_dialogues = []

    for log_file in log_files:
        dialogues = parse_log_file(log_file)

        # 最大数に制限
        dialogues = dialogues[:max_dialogues_per_file]

        all_dialogues.extend(dialogues)

    print()
    print(f"✓ Total dialogues extracted: {len(all_dialogues)}")
    print()

    if not all_dialogues:
        print("❌ No dialogues found. Check log file format.")
        return 1

    # === 学習サイクル実行 ===
    print("="*80)
    print("[Phase 3] Self-Improvement Learning Cycles")
    print("="*80)
    print()

    # 最大30対話まで
    learning_dialogues = all_dialogues[:30]

    print(f"Running {len(learning_dialogues)} learning cycles...")
    print()

    stats = loop.run_multiple_cycles(learning_dialogues)

    print()
    print("✓ Learning cycles complete")
    print()

    # === Cross空間構築 ===
    print("="*80)
    print("[Phase 4] Building Cross Space")
    print("="*80)
    print()

    concepts_list = list(miner.concepts.values())[:10]  # 最初の10個

    cross_objects = []
    for concept in concepts_list:
        try:
            cross_obj = cross_sim.create_from_concept(concept)
            cross_objects.append(cross_obj)
        except Exception as e:
            print(f"  ⚠️  Failed to create Cross object: {e}")

    print(f"✓ Cross objects created: {len(cross_objects)}")
    print()

    # === 世界モデル構築 ===
    print("="*80)
    print("[Phase 5] Building World Model")
    print("="*80)
    print()

    for concept in concepts_list:
        world_model.add_concept(concept)

    print(f"✓ Concepts added to world model: {len(world_model.concepts)}")

    world_model.build_relations()

    print()

    # 因果関係を学習 (隣接概念間)
    concepts_ids = list(world_model.concepts.keys())
    causality_learned = 0

    for i in range(min(5, len(concepts_ids) - 1)):
        world_model.learn_causality(concepts_ids[i], concepts_ids[i+1], observed=True)
        causality_learned += 1

    print(f"✓ Causality learned: {causality_learned} pairs")
    print()

    # === 動的コード生成テスト ===
    print("="*80)
    print("[Phase 6] Dynamic Code Generation")
    print("="*80)
    print()

    if cross_objects:
        test_obj = cross_objects[0]

        patterns = dynamic_gen.analyze_cross_patterns(test_obj.obj_id)
        print(f"✓ Patterns analyzed: {len(patterns.get('discovered_patterns', []))}")

        operations = dynamic_gen.discover_operations(patterns)
        print(f"✓ Operations discovered: {len(operations)}")

        dynamic_program = dynamic_gen.generate_from_cross_structure(
            test_obj.obj_id,
            "solve problem",
            context={}
        )

        print(f"✓ Dynamic program generated: {len(dynamic_program.split(chr(10)))} lines")
        print()

    # === XTS推論テスト ===
    print("="*80)
    print("[Phase 7] XTS Puzzle Reasoning")
    print("="*80)
    print()

    if concepts_list:
        solution = xts.solve_problem_with_xts(
            problem="apply learned concepts",
            concepts=concepts_list[:5],
            max_iterations=10
        )

        print(f"✓ XTS solution found")
        print(f"  Confidence: {solution['confidence']:.2f}")
        print()

    # === 最終統計 ===
    print("="*80)
    print("[Final Statistics]")
    print("="*80)
    print()

    print("Learning Results:")
    print(f"  Total dialogues processed: {len(learning_dialogues)}")
    print(f"  Concepts created: {stats['concepts_created']}")
    print(f"  Average score: {stats['average_score']:.2f}")
    print(f"  Total cycles: {stats['total_cycles']}")
    print()

    print("Miner Statistics:")
    miner_stats = miner.get_statistics()
    print(f"  Total concepts: {miner_stats['total_concepts']}")
    print(f"  Average confidence: {miner_stats['avg_confidence']:.2f}")
    print(f"  By domain: {miner_stats.get('by_domain', {})}")
    print()

    print("Cross Space:")
    print(f"  Objects: {len(cross_sim.objects)}")
    print(f"  Simulations: {len(cross_sim.simulation_history)}")
    print()

    print("Dynamic Generation:")
    dyn_stats = dynamic_gen.get_statistics()
    print(f"  Operations discovered: {dyn_stats['total_operations_discovered']}")
    print()

    print("XTS Reasoning:")
    xts_stats = xts.get_statistics()
    print(f"  Searches performed: {xts_stats.get('total_searches', 0)}")
    print()

    print("World Model:")
    wm_stats = world_model.get_statistics()
    print(f"  Total concepts: {wm_stats['total_concepts']}")
    print(f"  Total relations: {wm_stats['total_relations']}")
    print(f"  Total causality: {wm_stats['total_causality']}")
    print()

    # === 検証 ===
    print("="*80)
    print("[Verification]")
    print("="*80)
    print()

    success_criteria = {
        "Dialogues extracted": len(all_dialogues) > 0,
        "Learning completed": stats['total_cycles'] > 0,
        "Concepts created": stats['concepts_created'] > 0,
        "Average score acceptable": stats['average_score'] >= 0.5,
        "Cross space built": len(cross_sim.objects) > 0,
        "World model built": wm_stats['total_relations'] > 0,
    }

    all_passed = all(success_criteria.values())

    for criterion, passed in success_criteria.items():
        status = "✅" if passed else "❌"
        print(f"{status} {criterion}")

    print()

    if all_passed:
        print("="*80)
        print("🎉 REAL LOG LEARNING: SUCCESS! 🎉")
        print("="*80)
        print()
        print("Verantyxは実際のログから学習できました:")
        print(f"  ✅ {len(all_dialogues)} 対話を抽出")
        print(f"  ✅ {stats['concepts_created']} 概念を生成")
        print(f"  ✅ {stats['total_cycles']} 学習サイクル完了")
        print(f"  ✅ スコア {stats['average_score']:.2f}")
        print(f"  ✅ Cross空間: {len(cross_sim.objects)} オブジェクト")
        print(f"  ✅ 世界モデル: {wm_stats['total_relations']} 関係")
        print()
        print("🚀 実世界のログでの自己改善ループ: 動作確認完了")
        print()
        return 0
    else:
        print("⚠️  Some criteria not met")
        return 1


if __name__ == "__main__":
    log_files = [
        Path("/Users/motonishikoudai/avh.txt"),
        Path("/Users/motonishikoudai/claude.txt"),
        Path("/Users/motonishikoudai/hall.txt"),
        Path("/Users/motonishikoudai/hle.txt"),
        Path("/Users/motonishikoudai/oruborous.txt"),
        Path("/Users/motonishikoudai/verantyx-v.txt"),
        Path("/Users/motonishikoudai/verantyx-v3.txt"),
        Path("/Users/motonishikoudai/verantyx-v5.txt"),
        Path("/Users/motonishikoudai/verantyx-v7.txt"),
    ]

    exit(test_real_log_learning(log_files, max_dialogues_per_file=5))
