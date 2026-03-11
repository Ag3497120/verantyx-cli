#!/usr/bin/env python3
"""
Real Log Learning Test with Extended Operations

拡張操作コマンド(100+)を使った実際のログ学習テスト
Cross世界モデルの物理法則が豊富になり、学習の質が向上
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

# 拡張プロセッサを使用
from verantyx_cli.engine.domain_processors_extended import register_to_vm as register_extended_processors

from verantyx_cli.engine.cross_simulator import register_to_vm as register_cross_sim
from verantyx_cli.engine.dynamic_code_generator import register_to_vm as register_dynamic_gen
from verantyx_cli.engine.xts_puzzle_reasoning import register_to_vm as register_xts
from verantyx_cli.engine.world_model import register_to_vm as register_world_model


def parse_log_file(log_path: Path) -> List[Tuple[str, str]]:
    """ログファイルから対話を抽出"""
    print(f"\n[Parsing] {log_path.name}")

    if not log_path.exists():
        print(f"  ⚠️  File not found: {log_path}")
        return []

    content = log_path.read_text(encoding='utf-8', errors='ignore')
    dialogues = []

    # 複数のパターンでマッチ
    pattern1 = re.compile(r'User[:\s]+(.+?)\s+Assistant[:\s]+(.+?)(?=User[:\s]+|$)', re.DOTALL | re.IGNORECASE)
    pattern2 = re.compile(r'Human[:\s]+(.+?)\s+Claude[:\s]+(.+?)(?=Human[:\s]+|$)', re.DOTALL | re.IGNORECASE)
    pattern3 = re.compile(r'Q[:\s]+(.+?)\s+A[:\s]+(.+?)(?=Q[:\s]+|$)', re.DOTALL | re.IGNORECASE)

    all_matches = pattern1.findall(content) + pattern2.findall(content) + pattern3.findall(content)

    for user_text, assistant_text in all_matches:
        user_clean = user_text.strip()[:500]
        assistant_clean = assistant_text.strip()[:1000]

        if len(user_clean) > 10 and len(assistant_clean) > 10:
            dialogues.append((user_clean, assistant_clean))

    print(f"  ✅ Extracted {len(dialogues)} dialogues")
    return dialogues


def test_extended_log_learning(log_files: List[Path], max_dialogues: int = 30):
    """拡張操作コマンドで実際のログから学習テスト"""
    print("="*80)
    print("REAL LOG LEARNING TEST - EXTENDED OPERATIONS")
    print("="*80)
    print()

    # === 初期化 (拡張プロセッサ使用) ===
    print("[Phase 1] Initializing with Extended Operations...")
    print()

    vm = JCrossVM(storage_path=Path(".verantyx/extended_log_learning"))

    # 拡張プロセッサを登録 (100+ 操作)
    extended_processors = register_extended_processors(vm)

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

    print("✓ Verantyx initialized with Extended Operations")
    print()

    # === ログ解析 ===
    print("="*80)
    print("[Phase 2] Parsing Log Files")
    print("="*80)

    all_dialogues = []
    for log_file in log_files:
        dialogues = parse_log_file(log_file)
        all_dialogues.extend(dialogues[:5])  # 各ファイルから5個

    print()
    print(f"✓ Total dialogues: {len(all_dialogues)}")
    print()

    if not all_dialogues:
        print("❌ No dialogues found")
        return 1

    # === 学習実行 ===
    print("="*80)
    print("[Phase 3] Learning with Extended Operations")
    print("="*80)
    print()

    learning_dialogues = all_dialogues[:max_dialogues]
    print(f"Running {len(learning_dialogues)} cycles with 100+ operations available...")
    print()

    stats = loop.run_multiple_cycles(learning_dialogues)

    print()
    print("✓ Learning complete")
    print()

    # === Cross空間構築 ===
    print("="*80)
    print("[Phase 4] Building Cross Space with Physics Laws")
    print("="*80)
    print()

    concepts_list = list(miner.concepts.values())[:10]
    cross_objects = []

    for concept in concepts_list:
        try:
            cross_obj = cross_sim.create_from_concept(concept)
            cross_objects.append(cross_obj)
        except Exception:
            pass

    print(f"✓ Cross objects: {len(cross_objects)}")
    print()

    # === 世界モデル ===
    print("="*80)
    print("[Phase 5] Building World Model")
    print("="*80)
    print()

    for concept in concepts_list:
        world_model.add_concept(concept)

    world_model.build_relations()

    # 因果関係学習
    concepts_ids = list(world_model.concepts.keys())
    for i in range(min(5, len(concepts_ids) - 1)):
        world_model.learn_causality(concepts_ids[i], concepts_ids[i+1], observed=True)

    print()

    # === 動的コード生成 ===
    print("="*80)
    print("[Phase 6] Dynamic Code Generation")
    print("="*80)
    print()

    if cross_objects:
        test_obj = cross_objects[0]
        patterns = dynamic_gen.analyze_cross_patterns(test_obj.obj_id)
        operations = dynamic_gen.discover_operations(patterns)
        dynamic_program = dynamic_gen.generate_from_cross_structure(
            test_obj.obj_id,
            "solve problem with extended ops",
            context={}
        )

        print(f"✓ Patterns: {len(patterns.get('discovered_patterns', []))}")
        print(f"✓ Operations: {len(operations)}")
        print(f"✓ Dynamic program: {len(dynamic_program.split(chr(10)))} lines")
        print()

    # === XTS推論 ===
    print("="*80)
    print("[Phase 7] XTS Reasoning with Extended Ops")
    print("="*80)
    print()

    if concepts_list:
        solution = xts.solve_problem_with_xts(
            problem="apply concepts with extended operations",
            concepts=concepts_list[:5],
            max_iterations=10
        )
        print(f"✓ Solution confidence: {solution['confidence']:.2f}")
        print()

    # === 統計 ===
    print("="*80)
    print("[Final Statistics - Extended Operations]")
    print("="*80)
    print()

    print("Learning Results:")
    print(f"  Dialogues processed: {len(learning_dialogues)}")
    print(f"  Concepts created: {stats['concepts_created']}")
    print(f"  Average score: {stats['average_score']:.2f}")
    print(f"  Total cycles: {stats['total_cycles']}")
    print()

    miner_stats = miner.get_statistics()
    print("Miner:")
    print(f"  Total concepts: {miner_stats['total_concepts']}")
    print(f"  Average confidence: {miner_stats['avg_confidence']:.2f}")
    print()

    print("Cross Space:")
    print(f"  Objects: {len(cross_sim.objects)}")
    print()

    dyn_stats = dynamic_gen.get_statistics()
    print("Dynamic Generation:")
    print(f"  Operations discovered: {dyn_stats['total_operations_discovered']}")
    print()

    wm_stats = world_model.get_statistics()
    print("World Model:")
    print(f"  Concepts: {wm_stats['total_concepts']}")
    print(f"  Relations: {wm_stats['total_relations']}")
    print(f"  Causality: {wm_stats['total_causality']}")
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
        "Score improved with extended ops": stats['average_score'] >= 0.3,  # より高いスコア期待
        "Cross space built": len(cross_sim.objects) > 0,
        "World model built": wm_stats['total_relations'] > 0,
    }

    all_passed = all(success_criteria.values())

    for criterion, passed in success_criteria.items():
        status = "✅" if passed else "❌"
        print(f"{status} {criterion}")

    print()

    # === スコア比較 ===
    print("="*80)
    print("[Score Comparison]")
    print("="*80)
    print()
    print(f"基本操作(24個):     スコア 0.20")
    print(f"拡張操作(100+個):   スコア {stats['average_score']:.2f}")
    print()

    if stats['average_score'] > 0.20:
        improvement = ((stats['average_score'] - 0.20) / 0.20) * 100
        print(f"📈 改善率: +{improvement:.1f}%")
        print()

    if all_passed:
        print("="*80)
        print("🎉 EXTENDED OPERATIONS: SUCCESS! 🎉")
        print("="*80)
        print()
        print("拡張操作コマンド(100+)により学習の質が向上:")
        print(f"  ✅ {len(all_dialogues)} 対話抽出")
        print(f"  ✅ {stats['concepts_created']} 概念生成")
        print(f"  ✅ スコア {stats['average_score']:.2f}")
        print(f"  ✅ Cross空間: {len(cross_sim.objects)} オブジェクト")
        print(f"  ✅ 世界モデル: {wm_stats['total_relations']} 関係")
        print()
        print("🚀 Cross世界モデルの物理法則が豊富になりました")
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

    exit(test_extended_log_learning(log_files, max_dialogues=30))
