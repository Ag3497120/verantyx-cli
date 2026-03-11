#!/usr/bin/env python3
"""
JCross Program Generator - Verantyxの核心エンジン

思想:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    自然言語 → .jcross program → 検証可能な推論
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

これがVerantyxの本質:
    LLM (Claude) は回答を生成する
           ↓
    Verantyxは.jcrossプログラムを生成する
           ↓
    Cross Simulatorで検証する
           ↓
    検証済みの知識として蓄積する

AlphaGo的アプローチ:
    - NNは候補を提案
    - Tree Searchで検証
    - 最良の手を選択

Verantyxでは:
    - Task Structureから候補.jcrossを生成
    - Cross Simulatorで検証
    - 最良のプログラムを選択

これにより:
    ✓ 検証可能
    ✓ 説明可能
    ✓ 改善可能
    ✓ 個人最適化可能
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import re

from .task_structure_extractor import TaskStructure
from .cross_world_model import CrossWorldModel, CrossObject


@dataclass
class JCrossProgram:
    """
    .jcrossプログラム

    Verantyxの思想:
    - 自然言語の意味を保持
    - 実行可能な形式
    - 検証可能
    """
    program_id: str
    name: str
    code: str
    source_task_id: str

    # メタ情報
    concept_templates: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    verified: bool = False

    def to_dict(self) -> Dict:
        return {
            "program_id": self.program_id,
            "name": self.name,
            "code": self.code,
            "source_task_id": self.source_task_id,
            "concept_templates": self.concept_templates,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "verified": self.verified
        }

    def save(self, filepath: Path):
        """ファイルに保存"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.code)


class JCrossTemplateLibrary:
    """
    .jcrossテンプレートライブラリ

    Concept Templates:
    - パターンの再利用可能な骨格
    - パラメータで柔軟に適用
    """

    def __init__(self):
        self.templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict[str, str]:
        """基本テンプレートを初期化"""
        return {
            # ===== 問題解決テンプレート =====
            "error_diagnosis": """
# エラー診断プログラム
ラベル ErrorDiagnosis_{domain}
  # エラーメッセージを解析
  実行する パターンを抽出 "{error_pattern}"
  取り出す エラーパターン

  # 類似エラーを検索
  実行する 類似パターンを探索 エラーパターン
  取り出す 類似リスト

  # 解決策を提案
  繰り返す 解決策 in 類似リスト:
    条件 解決策.信頼度 > 0.7:
      出力する 解決策.手順
    条件終了
  繰り返し終了

  返す 類似リスト
""",

            "sequential_task": """
# 順次実行タスク
ラベル SequentialTask_{task_name}
  # ステップ実行
  {steps}

  # 成功判定
  条件 全ステップ成功:
    出力する "タスク完了"
    返す 成功
  条件でなければ:
    出力する "タスク失敗"
    返す 失敗
  条件終了
""",

            "tool_chain": """
# ツールチェーン実行
ラベル ToolChain_{chain_name}
  {tool_calls}

  返す 結果
""",

            # ===== パターン推論テンプレート =====
            "pattern_matching": """
# パターンマッチング
ラベル PatternMatch_{pattern_name}
  実行する パターンを抽出 "{input}"
  取り出す 入力パターン

  実行する 関連パターンを6軸で収集 入力パターン
  取り出す 関連Cross

  # UP×DOWN マッチング（抽象-具体）
  実行する パズルピースを組み合わせ 関連Cross
  取り出す 推論候補

  # 最適推論を選択
  実行する 最適推論を選択 推論候補
  取り出す 最適推論

  返す 最適推論
""",

            # ===== 小世界シミュレーション =====
            "world_simulation": """
# 小世界シミュレーション
ラベル WorldSim_{world_name}
  # 小世界構築
  実行する 小世界を構築 学習履歴
  取り出す 小世界Cross

  # パターン分析
  実行する パターン分析 小世界Cross.BACK
  取り出す パターン

  # 因果推論
  実行する 因果推論 パターン
  取り出す 因果関係

  # 未来予測
  実行する 未来を予測 小世界Cross
  取り出す 予測リスト

  返す 予測リスト
""",

            # ===== 学習テンプレート =====
            "knowledge_update": """
# 知識更新
ラベル KnowledgeUpdate_{concept}
  # 既存知識取得
  実行する 知識を検索 "{concept}"
  取り出す 既存知識

  # 新規知識と統合
  実行する 知識を統合 既存知識 新規知識
  取り出す 統合知識

  # 信頼度更新
  実行する 信頼度を計算 統合知識
  取り出す 新信頼度

  # 保存
  実行する 知識を保存 統合知識 新信頼度

  返す 統合知識
""",

            # ===== ユーザーモデル =====
            "user_preference": """
# ユーザー選好学習
ラベル UserPreference_{pref_type}
  # 過去の選択を分析
  実行する ユーザー履歴を取得 "{user_id}"
  取り出す 履歴

  実行する 選好パターンを抽出 履歴
  取り出す 選好

  # ドメイン別に分類
  繰り返す ドメイン in 選好.ドメインリスト:
    実行する ドメイン選好を更新 ドメイン 選好
  繰り返し終了

  返す 選好
"""
        }

    def get_template(self, template_name: str) -> Optional[str]:
        """テンプレートを取得"""
        return self.templates.get(template_name)

    def list_templates(self) -> List[str]:
        """利用可能なテンプレート一覧"""
        return list(self.templates.keys())


class JCrossProgramGenerator:
    """
    .jcrossプログラム生成エンジン

    Verantyxの核心:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        TaskStructure → .jcross program
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    プロセス:
    1. タスク分析
    2. 適切なテンプレート選択
    3. パラメータ抽出
    4. プログラム生成
    5. 検証（Cross Simulator）
    """

    def __init__(self, cross_world: Optional[CrossWorldModel] = None):
        self.cross_world = cross_world or CrossWorldModel()
        self.template_library = JCrossTemplateLibrary()

        # 生成統計
        self.stats = {
            "programs_generated": 0,
            "programs_verified": 0,
            "templates_used": {}
        }

    def generate_from_task(
        self,
        task: TaskStructure,
        verify: bool = True
    ) -> List[JCrossProgram]:
        """
        TaskStructureから.jcrossプログラムを生成

        Args:
            task: タスク構造
            verify: 検証するか

        Returns:
            生成されたプログラムのリスト（複数候補）
        """
        programs = []

        # 1. タスクタイプに応じてテンプレート選択
        template_candidates = self._select_templates(task)

        # 2. 各テンプレートからプログラム生成
        for template_name in template_candidates:
            program = self._generate_from_template(
                task=task,
                template_name=template_name
            )
            if program:
                programs.append(program)

        # 3. 検証
        if verify:
            programs = [p for p in programs if self._verify_program(p)]

        # 統計更新
        self.stats["programs_generated"] += len(programs)
        self.stats["programs_verified"] += sum(1 for p in programs if p.verified)

        return programs

    def _select_templates(self, task: TaskStructure) -> List[str]:
        """タスクに適したテンプレートを選択"""
        templates = []

        # 問題タイプに応じて選択
        if task.problem_type == "error":
            templates.append("error_diagnosis")

        if task.solution_steps:
            templates.append("sequential_task")

        if task.tools_used:
            templates.append("tool_chain")

        # 意図に応じて選択
        if task.intent == "question":
            templates.append("pattern_matching")

        # デフォルト
        if not templates:
            templates.append("sequential_task")

        return templates

    def _generate_from_template(
        self,
        task: TaskStructure,
        template_name: str
    ) -> Optional[JCrossProgram]:
        """テンプレートからプログラムを生成"""
        template = self.template_library.get_template(template_name)
        if not template:
            return None

        # パラメータ抽出
        params = self._extract_parameters(task, template_name)

        # テンプレート展開
        code = self._expand_template(template, params)

        program = JCrossProgram(
            program_id=f"jcross_{task.task_id}_{template_name}",
            name=f"{template_name}_{task.domain}",
            code=code,
            source_task_id=task.task_id,
            concept_templates=[template_name],
            parameters=params,
            confidence=task.confidence
        )

        # 統計更新
        if template_name not in self.stats["templates_used"]:
            self.stats["templates_used"][template_name] = 0
        self.stats["templates_used"][template_name] += 1

        return program

    def _extract_parameters(
        self,
        task: TaskStructure,
        template_name: str
    ) -> Dict[str, Any]:
        """テンプレートパラメータを抽出"""
        params = {
            "domain": task.domain,
            "task_name": self._sanitize_name(task.goal),
            "user_input": task.user_input
        }

        # テンプレート別パラメータ
        if template_name == "error_diagnosis":
            params["error_pattern"] = self._extract_error_pattern(task.user_input)

        elif template_name == "sequential_task":
            params["steps"] = self._format_steps(task.solution_steps)

        elif template_name == "tool_chain":
            params["chain_name"] = "_".join(task.tools_used)
            params["tool_calls"] = self._format_tool_calls(task.solution_steps, task.tools_used)

        elif template_name == "pattern_matching":
            params["pattern_name"] = self._sanitize_name(task.goal)
            params["input"] = task.user_input

        return params

    def _expand_template(self, template: str, params: Dict[str, Any]) -> str:
        """テンプレートを展開"""
        code = template

        # パラメータ置換
        for key, value in params.items():
            placeholder = f"{{{key}}}"
            if placeholder in code:
                code = code.replace(placeholder, str(value))

        return code

    def _sanitize_name(self, name: str) -> str:
        """名前をサニタイズ"""
        # 英数字とアンダースコアのみ
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        return sanitized[:50]  # 最大50文字

    def _extract_error_pattern(self, text: str) -> str:
        """エラーパターンを抽出"""
        # "error", "エラー" を含む部分を抽出
        error_keywords = ["error", "エラー", "failed", "失敗"]
        for keyword in error_keywords:
            if keyword in text.lower():
                # キーワード周辺30文字を抽出
                idx = text.lower().find(keyword)
                start = max(0, idx - 15)
                end = min(len(text), idx + 15)
                return text[start:end].strip()
        return "不明なエラー"

    def _format_steps(self, steps: List[str]) -> str:
        """ステップをフォーマット"""
        if not steps:
            return '  出力する "ステップなし"'

        formatted_lines = []
        for i, step in enumerate(steps, 1):
            # ステップをサニタイズ
            step_clean = step.replace('"', '\\"')[:100]
            formatted_lines.append(f'  出力する "Step {i}: {step_clean}"')

        return "\n".join(formatted_lines)

    def _format_tool_calls(self, steps: List[str], tools: List[str]) -> str:
        """ツール呼び出しをフォーマット"""
        if not tools:
            return '  出力する "ツールなし"'

        formatted_lines = []
        for tool in tools:
            formatted_lines.append(f'  実行する ツールを起動 "{tool}"')
            formatted_lines.append(f'  取り出す {tool}_結果')

        return "\n".join(formatted_lines)

    def _verify_program(self, program: JCrossProgram) -> bool:
        """
        プログラムを検証

        現在: 基本的な文法チェック
        将来: Cross Simulatorで実行検証
        """
        code = program.code

        # 基本チェック
        if not code.strip():
            return False

        # ラベル存在チェック
        if "ラベル" not in code:
            return False

        # 対応チェック
        if code.count("条件") != code.count("条件終了"):
            return False

        if code.count("繰り返す") != code.count("繰り返し終了"):
            return False

        program.verified = True
        return True

    def generate_solution_template(
        self,
        task: TaskStructure,
        similar_tasks: List[TaskStructure]
    ) -> Optional[JCrossProgram]:
        """
        類似タスクから解決テンプレートを生成

        これがVerantyxの学習メカニズム:
        - 過去の解決策を分析
        - 共通パターンを抽出
        - 新しいテンプレートを生成
        """
        if len(similar_tasks) < 2:
            return None

        # 共通ステップを抽出
        common_steps = self._extract_common_steps(similar_tasks)

        # テンプレート生成
        template_code = f"""
# 自動生成テンプレート: {task.domain}_{task.problem_type}
ラベル AutoTemplate_{task.domain}_{task.problem_type}
  # 共通手順
{self._format_steps(common_steps)}

  返す 成功
"""

        program = JCrossProgram(
            program_id=f"auto_template_{task.domain}_{task.problem_type}",
            name=f"AutoTemplate_{task.domain}",
            code=template_code,
            source_task_id=task.task_id,
            concept_templates=["auto_generated"],
            parameters={"source_tasks": [t.task_id for t in similar_tasks]},
            confidence=0.7
        )

        return program

    def _extract_common_steps(self, tasks: List[TaskStructure]) -> List[str]:
        """複数タスクから共通ステップを抽出"""
        if not tasks:
            return []

        # 最初のタスクのステップを基準
        base_steps = set(tasks[0].solution_steps)

        # 全タスクで共通するステップ
        for task in tasks[1:]:
            base_steps &= set(task.solution_steps)

        return list(base_steps)

    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        return self.stats.copy()
