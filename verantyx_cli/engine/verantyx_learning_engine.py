#!/usr/bin/env python3
"""
Verantyx Learning Engine - 統合学習エンジン

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verantyxの完全な思想を実現する統合エンジン
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

フロー:
    Claude対話ログ
         ↓
    Task Structure Extraction (意味構造化)
         ↓
    .jcross Program Generation (プログラム合成)
         ↓
    Cross Simulator (検証)
         ↓
    Cross World Model (知識蓄積)
         ↓
    User Knowledge Model (個人最適化)

これにより:
✓ Claude出力から学習
✓ 検証可能な知識
✓ 個人専用AI
✓ 継続的改善
"""

from typing import Optional, Dict, List, Any, Callable
from pathlib import Path
from datetime import datetime
import json

from .cross_world_model import CrossWorldModel
from .task_structure_extractor import TaskStructureExtractor, TaskStructure
from .jcross_program_generator import JCrossProgramGenerator, JCrossProgram
from .cross_simulator_enhanced import CrossSimulatorEnhanced, SimulationResult
from .user_knowledge_model import UserKnowledgeModel


class VerantyxLearningEngine:
    """
    Verantyx統合学習エンジン

    claude_subprocess_engineから呼び出される
    """

    def __init__(
        self,
        user_id: str = "default",
        project_path: Optional[Path] = None,
        on_learning_event: Optional[Callable] = None
    ):
        self.user_id = user_id
        self.project_path = project_path or Path(".")
        self.verantyx_dir = self.project_path / ".verantyx"
        self.verantyx_dir.mkdir(exist_ok=True)

        # コールバック
        self.on_learning_event = on_learning_event

        # コアコンポーネント初期化
        self.cross_world = CrossWorldModel()
        self.task_extractor = TaskStructureExtractor(self.cross_world)
        self.program_generator = JCrossProgramGenerator(self.cross_world)
        self.simulator = CrossSimulatorEnhanced(self.cross_world)
        self.user_model = UserKnowledgeModel(user_id, self.verantyx_dir / "users")

        # 学習履歴
        self.learning_history: List[Dict] = []

        # 統計
        self.stats = {
            "total_dialogues": 0,
            "tasks_extracted": 0,
            "programs_generated": 0,
            "programs_verified": 0,
            "learning_accelerations": 0
        }

        # 既存データ読み込み
        self._load_existing_data()

    def _load_existing_data(self):
        """既存のCross World Modelを読み込み"""
        world_file = self.verantyx_dir / "cross_world.json"
        if world_file.exists():
            try:
                self.cross_world = CrossWorldModel.load_from_file(str(world_file))
                print(f"✅ Cross World loaded: {len(self.cross_world.objects)} objects")
            except Exception as e:
                print(f"⚠️  Failed to load Cross World: {e}")

    def process_dialogue(
        self,
        user_input: str,
        claude_response: str
    ) -> Dict[str, Any]:
        """
        対話を処理してCross構造を学習

        Returns:
            処理結果の辞書
        """
        self.stats["total_dialogues"] += 1

        result = {
            "dialogue_id": len(self.learning_history),
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "claude_response": claude_response,
            "task": None,
            "programs": [],
            "simulation": None,
            "learning_event": None
        }

        try:
            # 1. Task Structure Extraction
            task, registered_ids = self.task_extractor.extract_and_register(
                user_input=user_input,
                claude_response=claude_response
            )

            result["task"] = task.to_dict()
            self.stats["tasks_extracted"] += 1

            self._emit_event("task_extracted", task)

            # 2. .jcross Program Generation
            programs = self.program_generator.generate_from_task(
                task=task,
                verify=True
            )

            result["programs"] = [p.to_dict() for p in programs]
            self.stats["programs_generated"] += len(programs)

            if programs:
                self._emit_event("programs_generated", programs)

            # 3. Cross Simulation (検証)
            if programs:
                simulation = self.simulator.test_multiple_hypotheses(
                    programs=programs,
                    max_hypotheses=3
                )

                result["simulation"] = simulation.to_dict()

                if simulation.verified:
                    self.stats["programs_verified"] += 1
                    self._emit_event("program_verified", simulation.best_hypothesis)

            # 4. User Model Update
            self.user_model.update_from_task(task)

            # 5. 学習イベント判定
            learning_event = self._check_learning_milestones()
            if learning_event:
                result["learning_event"] = learning_event
                self._emit_event("learning_milestone", learning_event)

            # 履歴に追加
            self.learning_history.append(result)

            # 定期保存
            if len(self.learning_history) % 10 == 0:
                self._save_state()

        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Learning error: {e}")

        return result

    def _check_learning_milestones(self) -> Optional[Dict]:
        """学習マイルストーンをチェック"""
        dialogue_count = self.stats["total_dialogues"]

        # 3対話: パターン推論開始
        if dialogue_count == 3:
            return {
                "type": "pattern_inference_start",
                "message": "パターン推論が開始されました（3対話到達）"
            }

        # 5対話: 小世界シミュレータ開始
        if dialogue_count == 5:
            return {
                "type": "world_simulation_start",
                "message": "小世界シミュレータが開始されました（5対話到達）"
            }

        # 10対話: 学習加速
        if dialogue_count == 10:
            self.stats["learning_accelerations"] += 1
            return {
                "type": "learning_acceleration",
                "message": "学習が加速しています（10対話到達）"
            }

        return None

    def _emit_event(self, event_type: str, data: Any):
        """学習イベントを発火"""
        if self.on_learning_event:
            try:
                self.on_learning_event(event_type, data)
            except Exception as e:
                print(f"⚠️  Event callback error: {e}")

    def _save_state(self):
        """状態を保存"""
        # Cross World Model
        world_file = self.verantyx_dir / "cross_world.json"
        self.cross_world.save_to_file(str(world_file))

        # 学習履歴
        history_file = self.verantyx_dir / "learning_history.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(self.learning_history, f, ensure_ascii=False, indent=2)

        # 統計
        stats_file = self.verantyx_dir / "learning_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        return {
            **self.stats,
            "cross_world": self.cross_world.get_statistics(),
            "user_profile": {
                "user_id": self.user_model.user_id,
                "total_interactions": self.user_model.profile.total_interactions,
                "success_rate": self.user_model.profile.success_rate,
                "domains": len(self.user_model.profile.domains),
                "tools": len(self.user_model.profile.tools)
            }
        }

    def shutdown(self):
        """シャットダウン時の保存"""
        self._save_state()
        print("\n✅ Verantyx Learning Engine saved")
