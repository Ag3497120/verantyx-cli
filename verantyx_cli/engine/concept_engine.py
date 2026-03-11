#!/usr/bin/env python3
"""
Concept Engine - Verantyxの真の核心

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verantyx = Concept Discovery System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

思想:
    問題 + 回答 → 概念

    LLMは回答を生成する
         ↓
    Concept Engineは概念を抽出する
         ↓
    .jcrossは概念を実行可能にする
         ↓
    Cross Simulatorは概念を検証する

これがVerantyxの本質:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Concept = 問題解決の抽象化された知識
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

例:
    問題: "docker build error"
    回答: "check Dockerfile, rebuild image"
         ↓
    Concept: "build-failure-recovery"
         ↓
    Rule: check_config → rebuild
         ↓
    .jcross: 実行可能プログラム

François Chollet (ARC-AGI) の思想:
    "知能 = 新しい概念を発見する能力"

Verantyxの実現:
    Claude対話 → Concept Discovery → 再利用可能な知識
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re
import json
from pathlib import Path

from .task_structure_extractor import TaskStructure


@dataclass
class Concept:
    """
    概念 (Concept)

    Verantyxの知識の基本単位

    属性:
        - name: 概念名（例: "build-failure-recovery"）
        - rule: 抽象化されたルール
        - inputs: 入力条件
        - outputs: 出力結果
        - examples: 具体例
        - success_count: 成功回数
        - confidence: 確信度
    """
    concept_id: str
    name: str
    domain: str

    # 概念の本質
    rule: str                              # 抽象ルール
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    # 学習データ
    examples: List[Dict] = field(default_factory=list)  # 具体例
    source_tasks: List[str] = field(default_factory=list)  # ソースタスク

    # 統計
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.5

    # メタデータ
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "concept_id": self.concept_id,
            "name": self.name,
            "domain": self.domain,
            "rule": self.rule,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "examples": self.examples,
            "source_tasks": self.source_tasks,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def update_confidence(self):
        """信頼度を更新"""
        total = self.success_count + self.failure_count
        if total > 0:
            self.confidence = self.success_count / total
        self.updated_at = datetime.now().isoformat()


@dataclass
class ConceptIR:
    """
    Concept Intermediate Representation

    概念の中間表現（.jcross生成前）
    """
    concept: Concept
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_jcross_template(self) -> str:
        """
        .jcrossテンプレートに変換

        これがVerantyxの核心プロセス:
            Concept → .jcross template
        """
        return f"""
# Concept: {self.concept.name}
# Domain: {self.concept.domain}
# Rule: {self.concept.rule}

ラベル {self._sanitize_name(self.concept.name)}
  # Inputs: {', '.join(self.concept.inputs)}

  {self._generate_rule_code()}

  # Outputs: {', '.join(self.concept.outputs)}
  返す 結果
"""

    def _sanitize_name(self, name: str) -> str:
        """名前をサニタイズ"""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)

    def _generate_rule_code(self) -> str:
        """ルールから.jcrossコードを生成"""
        rule = self.concept.rule

        # 簡易的な変換
        if "check" in rule.lower():
            return '  実行する 確認する "状態"'
        elif "rebuild" in rule.lower():
            return '  実行する 再構築する "対象"'
        else:
            return f'  実行する 処理する "{rule}"'


class ConceptEngine:
    """
    Concept Engine - 概念発見システム

    役割:
    1. Claude対話から概念を抽出
    2. 概念をConceptグラフに登録
    3. 類似概念の検索
    4. 概念の統合・進化

    これがVerantyxをユニークにする:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        LLMの知識を概念として構造化 → 再利用可能
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(".verantyx/concepts")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 概念データベース
        self.concepts: Dict[str, Concept] = {}

        # ドメイン別インデックス
        self.domain_index: Dict[str, Set[str]] = {}

        # ルールパターン辞書
        self.rule_patterns = self._initialize_rule_patterns()

        # 統計
        self.stats = {
            "concepts_discovered": 0,
            "concepts_reused": 0,
            "concepts_evolved": 0
        }

        # 既存概念を読み込み
        self._load_concepts()

    def _initialize_rule_patterns(self) -> Dict[str, str]:
        """ルールパターンを初期化"""
        return {
            # エラー対応パターン
            "error_diagnosis": "analyze_error → identify_cause",
            "error_recovery": "check_state → fix_issue → verify",

            # ビルドパターン
            "build_failure_recovery": "check_config → rebuild",
            "dependency_resolution": "identify_missing → install → retry",

            # データ処理パターン
            "data_transformation": "load_data → transform → save",
            "data_analysis": "load_data → analyze → visualize",

            # デバッグパターン
            "step_debugging": "set_breakpoint → inspect → fix",
            "log_analysis": "collect_logs → parse → identify_issue",

            # 最適化パターン
            "performance_optimization": "profile → identify_bottleneck → optimize",
            "resource_optimization": "measure_usage → reduce → verify"
        }

    # ========================================
    # Concept Discovery
    # ========================================

    def discover_concept(
        self,
        task: TaskStructure,
        force_new: bool = False
    ) -> Tuple[Concept, bool]:
        """
        タスクから概念を発見

        Args:
            task: タスク構造
            force_new: 強制的に新規概念を作成

        Returns:
            (概念, 新規作成かどうか)
        """
        # 1. 類似概念を検索
        if not force_new:
            similar = self.find_similar_concepts(task)
            if similar:
                # 既存概念を更新
                concept = similar[0][0]
                self._update_concept(concept, task)
                self.stats["concepts_reused"] += 1
                return concept, False

        # 2. 新規概念を作成
        concept = self._extract_concept(task)
        self.concepts[concept.concept_id] = concept

        # インデックス更新
        if concept.domain not in self.domain_index:
            self.domain_index[concept.domain] = set()
        self.domain_index[concept.domain].add(concept.concept_id)

        self.stats["concepts_discovered"] += 1

        # 保存
        self._save_concept(concept)

        return concept, True

    def _extract_concept(self, task: TaskStructure) -> Concept:
        """
        タスクから概念を抽出

        これがVerantyxの核心ロジック:
            問題 + 解決策 → 抽象概念
        """
        # 概念名を生成
        concept_name = self._generate_concept_name(task)

        # ルールを抽出
        rule = self._extract_rule(task)

        # 入出力を抽出
        inputs = self._extract_inputs(task)
        outputs = self._extract_outputs(task)

        # 具体例を作成
        example = {
            "user_input": task.user_input,
            "claude_response": task.claude_response,
            "steps": task.solution_steps,
            "tools": task.tools_used
        }

        concept = Concept(
            concept_id=f"concept_{len(self.concepts)}",
            name=concept_name,
            domain=task.domain,
            rule=rule,
            inputs=inputs,
            outputs=outputs,
            examples=[example],
            source_tasks=[task.task_id],
            confidence=task.confidence
        )

        return concept

    def _generate_concept_name(self, task: TaskStructure) -> str:
        """概念名を生成"""
        # ドメイン + 問題タイプ
        base = f"{task.domain}_{task.problem_type}"

        # キーワードを追加
        if task.tools_used:
            tool = task.tools_used[0]
            base = f"{tool}_{task.problem_type}"

        return base.replace(" ", "_").lower()

    def _extract_rule(self, task: TaskStructure) -> str:
        """ルールを抽出"""
        # 既知のパターンにマッチするか
        for pattern_name, pattern_rule in self.rule_patterns.items():
            if self._matches_pattern(task, pattern_name):
                return pattern_rule

        # 解決手順から生成
        if len(task.solution_steps) >= 2:
            step1 = task.solution_steps[0][:20]
            step2 = task.solution_steps[1][:20] if len(task.solution_steps) > 1 else "complete"
            return f"{step1} → {step2}"

        return "analyze → solve"

    def _matches_pattern(self, task: TaskStructure, pattern_name: str) -> bool:
        """パターンにマッチするか"""
        text = (task.user_input + " " + task.claude_response).lower()

        keywords = {
            "error_recovery": ["error", "エラー", "fix", "修正"],
            "build_failure_recovery": ["build", "ビルド", "compile"],
            "dependency_resolution": ["dependency", "依存", "install"],
            "data_analysis": ["data", "データ", "analyze", "分析"],
            "performance_optimization": ["performance", "パフォーマンス", "optimize", "最適化"]
        }

        pattern_keywords = keywords.get(pattern_name, [])
        return any(kw in text for kw in pattern_keywords)

    def _extract_inputs(self, task: TaskStructure) -> List[str]:
        """入力を抽出"""
        inputs = []

        # ドメイン
        if task.domain != "general":
            inputs.append(f"domain:{task.domain}")

        # ツール
        for tool in task.tools_used:
            inputs.append(f"tool:{tool}")

        # 問題タイプ
        inputs.append(f"problem:{task.problem_type}")

        return inputs

    def _extract_outputs(self, task: TaskStructure) -> List[str]:
        """出力を抽出"""
        outputs = []

        # 解決策
        if task.solution_steps:
            outputs.append(f"steps:{len(task.solution_steps)}")

        # 期待結果
        outputs.append("success:boolean")

        return outputs

    def _update_concept(self, concept: Concept, task: TaskStructure):
        """既存概念を更新"""
        # 具体例を追加
        example = {
            "user_input": task.user_input,
            "claude_response": task.claude_response,
            "steps": task.solution_steps,
            "tools": task.tools_used
        }
        concept.examples.append(example)
        concept.source_tasks.append(task.task_id)

        # 成功カウント更新（暫定的に全て成功とする）
        concept.success_count += 1
        concept.update_confidence()

        # 保存
        self._save_concept(concept)

    # ========================================
    # Concept Search
    # ========================================

    def find_similar_concepts(
        self,
        task: TaskStructure,
        threshold: float = 0.6
    ) -> List[Tuple[Concept, float]]:
        """
        類似概念を検索

        Returns:
            (概念, 類似度)のリスト
        """
        results = []

        # ドメインでフィルタ
        candidate_ids = self.domain_index.get(task.domain, set())

        for concept_id in candidate_ids:
            concept = self.concepts.get(concept_id)
            if not concept:
                continue

            similarity = self._calculate_similarity(concept, task)

            if similarity >= threshold:
                results.append((concept, similarity))

        # 類似度でソート
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:5]

    def _calculate_similarity(self, concept: Concept, task: TaskStructure) -> float:
        """概念とタスクの類似度を計算"""
        score = 0.0

        # ドメイン一致
        if concept.domain == task.domain:
            score += 0.3

        # 問題タイプ一致
        if task.problem_type in concept.name:
            score += 0.2

        # ツール一致
        concept_tools = [ex.get("tools", []) for ex in concept.examples]
        concept_tools_flat = [tool for tools in concept_tools for tool in tools]
        tool_overlap = len(set(task.tools_used) & set(concept_tools_flat))
        if task.tools_used:
            score += 0.3 * (tool_overlap / len(task.tools_used))

        # 確信度
        score += 0.2 * concept.confidence

        return min(score, 1.0)

    # ========================================
    # Concept Evolution
    # ========================================

    def evolve_concepts(self):
        """
        概念を進化させる

        複数の類似概念を統合して、より抽象的な概念を生成
        """
        # ドメインごとに処理
        for domain, concept_ids in self.domain_index.items():
            concepts = [self.concepts[cid] for cid in concept_ids if cid in self.concepts]

            if len(concepts) >= 3:
                # 類似概念グループを発見
                groups = self._find_concept_clusters(concepts)

                for group in groups:
                    if len(group) >= 3:
                        # 統合概念を生成
                        evolved = self._merge_concepts(group)
                        if evolved:
                            self.concepts[evolved.concept_id] = evolved
                            self.stats["concepts_evolved"] += 1

    def _find_concept_clusters(self, concepts: List[Concept]) -> List[List[Concept]]:
        """概念のクラスターを発見"""
        clusters = []
        used = set()

        for concept in concepts:
            if concept.concept_id in used:
                continue

            cluster = [concept]
            used.add(concept.concept_id)

            # 類似概念を探す
            for other in concepts:
                if other.concept_id in used:
                    continue

                # ルールが類似しているか
                if self._rules_similar(concept.rule, other.rule):
                    cluster.append(other)
                    used.add(other.concept_id)

            if len(cluster) >= 2:
                clusters.append(cluster)

        return clusters

    def _rules_similar(self, rule1: str, rule2: str) -> bool:
        """ルールが類似しているか"""
        words1 = set(rule1.lower().split())
        words2 = set(rule2.lower().split())

        overlap = len(words1 & words2)
        total = len(words1 | words2)

        return overlap / total > 0.5 if total > 0 else False

    def _merge_concepts(self, concepts: List[Concept]) -> Optional[Concept]:
        """複数の概念を統合"""
        if not concepts:
            return None

        # 最も成功している概念をベースに
        base = max(concepts, key=lambda c: c.success_count)

        # 統合概念を作成
        merged = Concept(
            concept_id=f"evolved_{len(self.concepts)}",
            name=f"{base.domain}_pattern",
            domain=base.domain,
            rule=base.rule,
            inputs=base.inputs,
            outputs=base.outputs,
            examples=[],
            source_tasks=[]
        )

        # 全ての具体例を統合
        for concept in concepts:
            merged.examples.extend(concept.examples)
            merged.source_tasks.extend(concept.source_tasks)
            merged.success_count += concept.success_count
            merged.failure_count += concept.failure_count

        merged.update_confidence()

        return merged

    # ========================================
    # Persistence
    # ========================================

    def _save_concept(self, concept: Concept):
        """概念を保存"""
        filepath = self.storage_path / f"{concept.concept_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(concept.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_concepts(self):
        """保存された概念を読み込み"""
        if not self.storage_path.exists():
            return

        for filepath in self.storage_path.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    concept = Concept(
                        concept_id=data["concept_id"],
                        name=data["name"],
                        domain=data["domain"],
                        rule=data["rule"],
                        inputs=data.get("inputs", []),
                        outputs=data.get("outputs", []),
                        examples=data.get("examples", []),
                        source_tasks=data.get("source_tasks", []),
                        success_count=data.get("success_count", 0),
                        failure_count=data.get("failure_count", 0),
                        confidence=data.get("confidence", 0.5),
                        created_at=data.get("created_at", ""),
                        updated_at=data.get("updated_at", "")
                    )
                    self.concepts[concept.concept_id] = concept

                    # インデックス更新
                    if concept.domain not in self.domain_index:
                        self.domain_index[concept.domain] = set()
                    self.domain_index[concept.domain].add(concept.concept_id)
            except Exception as e:
                print(f"⚠️  Failed to load concept {filepath}: {e}")

    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        return {
            "total_concepts": len(self.concepts),
            "concepts_by_domain": {
                domain: len(cids)
                for domain, cids in self.domain_index.items()
            },
            **self.stats
        }
