#!/usr/bin/env python3
"""
Task Structure Extractor - Claudeログからタスク構造を抽出

思想:
- 自然言語対話 → 構造化されたタスクグラフ
- 暗黙的な意図・手順・ツールを明示化
- Cross World Modelで表現

入力:
    ユーザー: "docker build error"
    Claude: "check Dockerfile, run docker build"

出力:
    TaskGraph {
        domain: "docker"
        problem: "build error"
        solution_steps: [
            "check Dockerfile",
            "run docker build"
        ]
        tools: ["docker"]
        success_indicator: implicit
    }

これがVerantyxの核心:
LLMの回答 → 構造化された知識
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import re
from datetime import datetime

from .cross_world_model import (
    CrossWorldModel,
    CrossObject,
    ObjectType,
    RelationType
)


@dataclass
class TaskStructure:
    """
    タスク構造

    Verantyxの思想:
    - ユーザーの暗黙的意図を明示化
    - 解決手順を構造化
    - ツール・ドメイン知識を抽出
    """
    # 基本情報
    task_id: str
    user_input: str
    claude_response: str

    # 抽出された構造
    domain: str = "general"
    problem_type: str = "unknown"
    goal: str = ""
    intent: str = ""

    # 解決情報
    solution_steps: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)

    # メタ情報
    confidence: float = 0.5
    success: Optional[bool] = None  # implicit feedback
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "task_id": self.task_id,
            "user_input": self.user_input,
            "claude_response": self.claude_response,
            "domain": self.domain,
            "problem_type": self.problem_type,
            "goal": self.goal,
            "intent": self.intent,
            "solution_steps": self.solution_steps,
            "tools_used": self.tools_used,
            "concepts": self.concepts,
            "confidence": self.confidence,
            "success": self.success,
            "timestamp": self.timestamp
        }


class TaskStructureExtractor:
    """
    タスク構造抽出エンジン

    機能:
    1. ドメイン識別
    2. 問題タイプ分類
    3. 解決手順抽出
    4. ツール・概念抽出
    5. Cross World Modelへの登録
    """

    def __init__(self, cross_world: Optional[CrossWorldModel] = None):
        self.cross_world = cross_world or CrossWorldModel()

        # ドメイン辞書（ユーザーログから学習）
        self.domain_keywords = {
            "docker": ["docker", "container", "dockerfile", "image", "build"],
            "python": ["python", "pip", "import", "module", "pandas", "numpy"],
            "git": ["git", "commit", "push", "pull", "branch", "merge"],
            "javascript": ["javascript", "node", "npm", "react", "vue"],
            "data_analysis": ["データ", "分析", "csv", "excel", "可視化"],
            "debugging": ["error", "エラー", "bug", "バグ", "fix", "修正"],
            "optimization": ["最適化", "性能", "パフォーマンス", "高速化", "遅い"]
        }

        # 問題タイプ辞書
        self.problem_patterns = {
            "error": ["error", "エラー", "failed", "失敗"],
            "performance": ["遅い", "重い", "速度", "最適化"],
            "implementation": ["実装", "作成", "追加", "create", "add"],
            "understanding": ["どう", "なぜ", "どのように", "explain", "what"],
            "debugging": ["直して", "修正", "fix", "debug"]
        }

        # ツール識別パターン
        self.tool_patterns = {
            "docker": r"\bdocker\b",
            "git": r"\bgit\b",
            "npm": r"\bnpm\b",
            "python": r"\bpython3?\b",
            "pip": r"\bpip3?\b",
            "pytest": r"\bpytest\b"
        }

    def extract(
        self,
        user_input: str,
        claude_response: str,
        task_id: Optional[str] = None
    ) -> TaskStructure:
        """
        タスク構造を抽出

        Args:
            user_input: ユーザー入力
            claude_response: Claude応答
            task_id: タスクID（省略時は自動生成）

        Returns:
            抽出されたタスク構造
        """
        if task_id is None:
            task_id = f"task_{datetime.now().timestamp()}"

        task = TaskStructure(
            task_id=task_id,
            user_input=user_input,
            claude_response=claude_response
        )

        # 1. ドメイン識別
        task.domain = self._identify_domain(user_input, claude_response)

        # 2. 問題タイプ識別
        task.problem_type = self._identify_problem_type(user_input)

        # 3. ゴール抽出
        task.goal = self._extract_goal(user_input)

        # 4. 意図識別
        task.intent = self._identify_intent(user_input)

        # 5. 解決手順抽出
        task.solution_steps = self._extract_solution_steps(claude_response)

        # 6. ツール抽出
        task.tools_used = self._extract_tools(user_input, claude_response)

        # 7. 概念抽出
        task.concepts = self._extract_concepts(user_input, claude_response)

        # 8. 確信度計算
        task.confidence = self._calculate_confidence(task)

        return task

    def _identify_domain(self, user_input: str, claude_response: str) -> str:
        """ドメインを識別"""
        text = (user_input + " " + claude_response).lower()

        domain_scores = {}
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                domain_scores[domain] = score

        if not domain_scores:
            return "general"

        return max(domain_scores.items(), key=lambda x: x[1])[0]

    def _identify_problem_type(self, user_input: str) -> str:
        """問題タイプを識別"""
        text = user_input.lower()

        for ptype, patterns in self.problem_patterns.items():
            if any(p in text for p in patterns):
                return ptype

        return "general_inquiry"

    def _extract_goal(self, user_input: str) -> str:
        """ゴールを抽出"""
        # 簡易版: ユーザー入力から最初の文を抽出
        sentences = re.split(r'[。.！!？?]', user_input)
        if sentences:
            return sentences[0].strip()
        return user_input[:100]

    def _identify_intent(self, user_input: str) -> str:
        """意図を識別"""
        text = user_input.lower()

        if any(marker in text for marker in ["?", "？", "教えて", "どう"]):
            return "question"
        elif any(marker in text for marker in ["作成", "追加", "実装", "create"]):
            return "creation_request"
        elif any(marker in text for marker in ["修正", "直して", "fix"]):
            return "fix_request"
        elif any(marker in text for marker in ["説明", "詳しく", "explain"]):
            return "explanation_request"
        else:
            return "general_statement"

    def _extract_solution_steps(self, claude_response: str) -> List[str]:
        """解決手順を抽出"""
        steps = []

        # パターン1: 番号付きリスト
        numbered = re.findall(r'\d+[.)]\s*(.+?)(?=\n|$)', claude_response)
        if numbered:
            steps.extend(numbered)

        # パターン2: 箇条書き
        bullets = re.findall(r'[-•*]\s*(.+?)(?=\n|$)', claude_response)
        if bullets:
            steps.extend(bullets)

        # パターン3: コマンド
        commands = re.findall(r'```[^`]*```', claude_response, re.DOTALL)
        if commands:
            for cmd_block in commands:
                # コードブロック内の各行
                lines = cmd_block.strip('`').split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        steps.append(f"Execute: {line}")

        # パターン4: "First, ...", "Then, ...", "Finally, ..."
        sequence_markers = re.findall(
            r'(?:first|then|next|finally|lastly)[,:]?\s*(.+?)(?=\.|$)',
            claude_response,
            re.IGNORECASE
        )
        if sequence_markers:
            steps.extend(sequence_markers)

        return [s.strip() for s in steps if s.strip()][:10]  # 上位10ステップ

    def _extract_tools(self, user_input: str, claude_response: str) -> List[str]:
        """ツールを抽出"""
        text = (user_input + " " + claude_response).lower()
        tools = []

        for tool, pattern in self.tool_patterns.items():
            if re.search(pattern, text):
                tools.append(tool)

        return tools

    def _extract_concepts(self, user_input: str, claude_response: str) -> List[str]:
        """概念を抽出"""
        text = (user_input + " " + claude_response)

        # 英単語・技術用語を抽出
        concepts = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', text)

        # 日本語の重要語を抽出（簡易版）
        ja_concepts = re.findall(r'[\u4e00-\u9fff]{2,6}', text)

        all_concepts = concepts + ja_concepts

        # 除外語
        exclude = {"The", "This", "That", "These", "Those", "して", "ください"}

        unique = list(dict.fromkeys(all_concepts))  # 順序を保持して重複除去
        return [c for c in unique if c not in exclude][:15]

    def _calculate_confidence(self, task: TaskStructure) -> float:
        """確信度を計算"""
        confidence = 0.5  # ベース

        # ドメイン識別の確信度
        if task.domain != "general":
            confidence += 0.1

        # 解決手順があれば加点
        if task.solution_steps:
            confidence += min(len(task.solution_steps) * 0.05, 0.2)

        # ツールが特定されていれば加点
        if task.tools_used:
            confidence += min(len(task.tools_used) * 0.05, 0.15)

        return min(confidence, 1.0)

    def register_to_cross_world(self, task: TaskStructure) -> Dict[str, str]:
        """
        Cross World Modelに登録

        Returns:
            登録されたオブジェクトIDの辞書
        """
        registered_ids = {}

        # 1. Taskオブジェクト作成
        task_obj = self.cross_world.add_object(
            obj_type=ObjectType.TASK,
            name=task.goal,
            properties={
                "user_input": task.user_input,
                "problem_type": task.problem_type,
                "intent": task.intent,
                "timestamp": task.timestamp
            },
            confidence=task.confidence
        )
        registered_ids["task"] = task_obj.id

        # 2. Domainオブジェクト作成（または取得）
        domain_objs = self.cross_world.find_objects_by_property(
            "name", task.domain
        )
        if domain_objs:
            domain_obj = domain_objs[0]
        else:
            domain_obj = self.cross_world.add_object(
                obj_type=ObjectType.DOMAIN,
                name=task.domain,
                properties={"type": "domain"}
            )
        registered_ids["domain"] = domain_obj.id

        # 3. Task → Domain の PART_OF 関係
        self.cross_world.add_relation(
            source_id=task_obj.id,
            target_id=domain_obj.id,
            relation_type=RelationType.PART_OF
        )

        # 4. Solutionオブジェクト作成
        if task.solution_steps:
            solution_obj = self.cross_world.add_object(
                obj_type=ObjectType.SOLUTION,
                name=f"Solution for {task.goal}",
                properties={
                    "steps": task.solution_steps,
                    "tools": task.tools_used
                },
                confidence=task.confidence
            )
            registered_ids["solution"] = solution_obj.id

            # Task → Solution の因果関係
            self.cross_world.add_relation(
                source_id=task_obj.id,
                target_id=solution_obj.id,
                relation_type=RelationType.CAUSES,
                strength=task.confidence
            )

        # 5. Toolオブジェクト作成
        for tool in task.tools_used:
            tool_objs = self.cross_world.find_objects_by_property("name", tool)
            if not tool_objs:
                tool_obj = self.cross_world.add_object(
                    obj_type=ObjectType.TOOL,
                    name=tool,
                    properties={"type": "tool"}
                )
            else:
                tool_obj = tool_objs[0]

            # Solution → Tool の REQUIRES 関係
            if "solution" in registered_ids:
                self.cross_world.add_relation(
                    source_id=registered_ids["solution"],
                    target_id=tool_obj.id,
                    relation_type=RelationType.REQUIRES
                )

        # 6. Conceptオブジェクト作成
        for concept in task.concepts[:5]:  # 上位5個
            concept_objs = self.cross_world.find_objects_by_property("name", concept)
            if not concept_objs:
                concept_obj = self.cross_world.add_object(
                    obj_type=ObjectType.CONCEPT,
                    name=concept,
                    properties={"type": "concept"}
                )
            else:
                concept_obj = concept_objs[0]

            # Task → Concept の関連
            self.cross_world.add_relation(
                source_id=task_obj.id,
                target_id=concept_obj.id,
                relation_type=RelationType.PART_OF,
                strength=0.5
            )

        return registered_ids

    def extract_and_register(
        self,
        user_input: str,
        claude_response: str,
        task_id: Optional[str] = None
    ) -> Tuple[TaskStructure, Dict[str, str]]:
        """
        抽出とCross World登録を一度に実行

        Returns:
            (TaskStructure, 登録されたオブジェクトID辞書)
        """
        task = self.extract(user_input, claude_response, task_id)
        registered_ids = self.register_to_cross_world(task)

        return task, registered_ids
