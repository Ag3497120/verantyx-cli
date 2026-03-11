#!/usr/bin/env python3
"""
.jcross VM (完全版)

Verantyxの核心: .jcrossプログラムが実際に動く

機能:
1. .jcross → 実行
2. Cross空間への Read/Write
3. Past経験の検索
4. 条件分岐・ループ
5. 関数呼び出し

設計思想:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    .jcross = 実行可能な知識表現
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
import re
import json
from datetime import datetime


# ========================================
# Cross空間
# ========================================

@dataclass
class CrossSpace:
    """
    Cross空間: 6軸構造での知識保持

    UP/DOWN: 抽象度
    LEFT/RIGHT: 時間軸
    FRONT/BACK: 因果関係
    """
    objects: Dict[str, Any] = field(default_factory=dict)

    # 空間別インデックス
    up_down: Dict[str, List[str]] = field(default_factory=lambda: {"up": [], "down": []})
    left_right: Dict[str, List[str]] = field(default_factory=lambda: {"left": [], "right": []})
    front_back: Dict[str, List[str]] = field(default_factory=lambda: {"front": [], "back": []})

    def store(self, key: str, value: Any, axis: Optional[str] = None):
        """Cross空間に保存"""
        self.objects[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
            "axis": axis
        }

        # 軸別インデックスに追加
        if axis:
            if axis in ["up", "down"]:
                self.up_down[axis].append(key)
            elif axis in ["left", "right"]:
                self.left_right[axis].append(key)
            elif axis in ["front", "back"]:
                self.front_back[axis].append(key)

    def retrieve(self, key: str) -> Optional[Any]:
        """Cross空間から取得"""
        if key in self.objects:
            return self.objects[key]["value"]
        return None

    def search_by_axis(self, axis: str) -> List[str]:
        """軸で検索"""
        if axis in ["up", "down"]:
            return self.up_down.get(axis, [])
        elif axis in ["left", "right"]:
            return self.left_right.get(axis, [])
        elif axis in ["front", "back"]:
            return self.front_back.get(axis, [])
        return []

    def search_similar(self, query: Any, top_k: int = 5) -> List[str]:
        """類似検索（簡易実装: 文字列マッチ）"""
        results = []
        query_str = str(query).lower()

        for key, obj in self.objects.items():
            value_str = str(obj["value"]).lower()
            if query_str in value_str or value_str in query_str:
                results.append(key)

        return results[:top_k]


# ========================================
# .jcross VM
# ========================================

class JCrossVM:
    """
    .jcross仮想マシン

    命令:
    - 取り出す <var>: スタックから変数に代入
    - 記憶する <key> <value>: Cross空間に保存
    - 実行する <operation> <args>: 操作を実行
    - もし <condition> なら: 条件分岐
    - 繰り返す <count>回: ループ
    - 返す <value>: 関数からreturn
    """

    def __init__(self, storage_path: Optional[Path] = None):
        # Cross空間
        self.cross_space = CrossSpace()

        # 変数スコープ
        self.variables: Dict[str, Any] = {}
        self.global_variables: Dict[str, Any] = {}

        # スタック
        self.stack: List[Any] = []

        # ラベル辞書（関数定義）
        self.labels: Dict[str, List[str]] = {}

        # 操作プロセッサ
        self.processors: Dict[str, Callable] = {}
        self._register_builtin_processors()

        # 実行状態
        self.pc = 0  # Program Counter
        self.instructions: List[str] = []

        # ストレージ
        self.storage_path = storage_path or Path(".verantyx/jcross_vm")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _register_builtin_processors(self):
        """組み込みプロセッサを登録"""

        # パターン抽出
        def extract_pattern(pattern: str, text: str) -> List[str]:
            return re.findall(pattern, text, re.IGNORECASE)

        # 抽象化
        def abstract(items: List[str]) -> str:
            # 簡易: 共通prefix抽出
            if not items:
                return ""
            if len(items) == 1:
                return items[0]

            # 最長共通部分文字列
            common = items[0]
            for item in items[1:]:
                i = 0
                while i < min(len(common), len(item)) and common[i] == item[i]:
                    i += 1
                common = common[:i]

            return common.strip() or "abstract_concept"

        # 類似度計算
        def similarity(a: str, b: str) -> float:
            a_set = set(a.lower().split())
            b_set = set(b.lower().split())

            if not a_set or not b_set:
                return 0.0

            intersection = a_set & b_set
            union = a_set | b_set

            return len(intersection) / len(union)

        self.processors["パターン抽出"] = extract_pattern
        self.processors["抽出"] = extract_pattern
        self.processors["抽象化"] = abstract
        self.processors["類似度計算"] = similarity
        self.processors["類似検索"] = lambda query, space: self.cross_space.search_similar(query)

    def register_processor(self, name: str, processor: Callable):
        """カスタムプロセッサを登録"""
        self.processors[name] = processor

    # ========================================
    # プログラム実行
    # ========================================

    def load_program(self, jcross_code: str):
        """
        .jcrossプログラムを読み込み

        ラベル定義を解析
        """
        lines = jcross_code.strip().split("\n")
        current_label = None
        current_body = []

        for line in lines:
            line = line.strip()

            # コメント除去
            if "#" in line:
                line = line.split("#")[0].strip()

            if not line:
                continue

            # ラベル定義
            if line.startswith("ラベル "):
                if current_label:
                    self.labels[current_label] = current_body

                current_label = line.replace("ラベル ", "").strip()
                current_body = []
            else:
                if current_label:
                    current_body.append(line)

        # 最後のラベル
        if current_label:
            self.labels[current_label] = current_body

    def execute_label(self, label_name: str, *args) -> Any:
        """
        ラベル（関数）を実行
        """
        if label_name not in self.labels:
            raise ValueError(f"Label '{label_name}' not found")

        # 引数をスタックにpush
        for arg in args:
            self.stack.append(arg)

        # 命令リストを取得
        self.instructions = self.labels[label_name]
        self.pc = 0

        # 実行ループ
        while self.pc < len(self.instructions):
            instruction = self.instructions[self.pc]
            result = self._execute_instruction(instruction)

            # 返す命令
            if result is not None and isinstance(result, tuple) and result[0] == "RETURN":
                return result[1]

            self.pc += 1

        # デフォルトreturn
        return None

    def _execute_instruction(self, instruction: str) -> Any:
        """
        命令を実行
        """
        tokens = instruction.split()

        if not tokens:
            return None

        cmd = tokens[0]

        # 取り出す
        if cmd == "取り出す":
            # 取り出す var1 var2 ...
            for var_name in tokens[1:]:
                if self.stack:
                    self.variables[var_name] = self.stack.pop(0)
                else:
                    self.variables[var_name] = None
            return None

        # 記憶する
        elif cmd == "記憶する":
            # 記憶する key value [axis]
            if len(tokens) < 3:
                return None

            key = tokens[1]
            value_name = tokens[2]
            axis = tokens[3] if len(tokens) > 3 else None

            value = self._resolve_value(value_name)
            self.cross_space.store(key, value, axis)
            return None

        # 実行する
        elif cmd == "実行する":
            # 実行する operation arg1 arg2 ...
            if len(tokens) < 2:
                return None

            operation = tokens[1]
            args = [self._resolve_value(arg) for arg in tokens[2:]]

            result = self._execute_operation(operation, args)

            # 結果を"結果"変数に保存
            self.variables["結果"] = result

            return None

        # もし
        elif cmd == "もし":
            # もし condition なら
            condition = self._evaluate_condition(tokens[1:])

            if condition:
                # 次の命令を実行
                pass
            else:
                # "そうでなければ" または "終わり" まで skip
                self._skip_to_else_or_end()

            return None

        # そうでなければ
        elif cmd == "そうでなければ":
            # if blockが実行されたのでskip
            self._skip_to_end()
            return None

        # 終わり
        elif cmd == "終わり":
            return None

        # 繰り返す
        elif cmd == "繰り返す":
            # 繰り返す N回
            count_str = tokens[1].replace("回", "")
            count = int(count_str)

            # ループ本体を取得
            loop_start = self.pc + 1
            loop_end = self._find_matching_end()

            for _ in range(count):
                for i in range(loop_start, loop_end):
                    self._execute_instruction(self.instructions[i])

            # ループ終了後、"終わり"の次へ
            self.pc = loop_end
            return None

        # 各〜に対して
        elif cmd == "各ログに対して" or cmd.startswith("各"):
            # TODO: implement iteration
            pass

        # 返す
        elif cmd == "返す":
            # 返す value
            if len(tokens) > 1:
                value = self._resolve_value(tokens[1])
            else:
                value = self.variables.get("結果")

            return ("RETURN", value)

        return None

    def _resolve_value(self, value_str: str) -> Any:
        """
        値を解決

        - 変数参照
        - リテラル
        - Cross空間参照
        """
        # 文字列リテラル
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]

        # 数値リテラル
        try:
            if "." in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass

        # 変数参照
        if value_str in self.variables:
            return self.variables[value_str]

        # Cross空間参照
        cross_value = self.cross_space.retrieve(value_str)
        if cross_value is not None:
            return cross_value

        # リテラルとして返す
        return value_str

    def _execute_operation(self, operation: str, args: List[Any]) -> Any:
        """
        操作を実行
        """
        if operation in self.processors:
            processor = self.processors[operation]
            try:
                return processor(*args)
            except Exception as e:
                print(f"⚠️  Operation '{operation}' failed: {e}")
                return None

        # ラベル呼び出し
        if operation in self.labels:
            return self.execute_label(operation, *args)

        print(f"⚠️  Unknown operation: {operation}")
        return None

    def _evaluate_condition(self, tokens: List[str]) -> bool:
        """
        条件を評価

        例: 類似度 > 0.7
        """
        if len(tokens) < 3:
            return False

        left = self._resolve_value(tokens[0])
        operator = tokens[1]
        right = self._resolve_value(tokens[2])

        try:
            if operator == ">":
                return float(left) > float(right)
            elif operator == "<":
                return float(left) < float(right)
            elif operator == "==":
                return left == right
            elif operator == "!=":
                return left != right
            elif operator == ">=":
                return float(left) >= float(right)
            elif operator == "<=":
                return float(left) <= float(right)
        except Exception:
            return False

        return False

    def _skip_to_else_or_end(self):
        """そうでなければ または 終わり までskip"""
        depth = 1
        while self.pc < len(self.instructions):
            self.pc += 1
            if self.pc >= len(self.instructions):
                break

            instruction = self.instructions[self.pc]
            if instruction.startswith("もし"):
                depth += 1
            elif instruction == "終わり":
                depth -= 1
                if depth == 0:
                    break
            elif instruction == "そうでなければ" and depth == 1:
                break

    def _skip_to_end(self):
        """終わり までskip"""
        depth = 1
        while self.pc < len(self.instructions):
            self.pc += 1
            if self.pc >= len(self.instructions):
                break

            instruction = self.instructions[self.pc]
            if instruction.startswith("もし") or instruction.startswith("繰り返す"):
                depth += 1
            elif instruction == "終わり":
                depth -= 1
                if depth == 0:
                    break

    def _find_matching_end(self) -> int:
        """対応する"終わり"を見つける"""
        depth = 1
        i = self.pc + 1
        while i < len(self.instructions):
            instruction = self.instructions[i]
            if instruction.startswith("繰り返す") or instruction.startswith("もし"):
                depth += 1
            elif instruction == "終わり":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return len(self.instructions)

    # ========================================
    # 永続化
    # ========================================

    def save_state(self):
        """状態を保存"""
        state = {
            "cross_space": {
                "objects": self.cross_space.objects,
                "up_down": self.cross_space.up_down,
                "left_right": self.cross_space.left_right,
                "front_back": self.cross_space.front_back
            },
            "global_variables": self.global_variables,
            "labels": self.labels
        }

        state_file = self.storage_path / "vm_state.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self):
        """状態を読み込み"""
        state_file = self.storage_path / "vm_state.json"
        if not state_file.exists():
            return

        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)

        # Cross空間を復元
        self.cross_space.objects = state["cross_space"]["objects"]
        self.cross_space.up_down = state["cross_space"]["up_down"]
        self.cross_space.left_right = state["cross_space"]["left_right"]
        self.cross_space.front_back = state["cross_space"]["front_back"]

        self.global_variables = state["global_variables"]
        self.labels = state["labels"]


# ========================================
# テスト
# ========================================

def test_jcross_vm():
    """VMテスト"""
    print("=" * 80)
    print(".jcross VM テスト")
    print("=" * 80)

    vm = JCrossVM()

    # テストプログラム
    program = """
# Docker Build Error診断

ラベル docker_build_error_診断
  # Input: エラーログ
  取り出す error_log

  # パターン抽出
  実行する パターン抽出 "FROM|COPY|RUN" error_log
  記憶する dockerfile_keywords 結果

  # 類似検索
  実行する 類似検索 dockerfile_keywords Cross空間
  記憶する similar_cases 結果

  # 類似度計算
  もし similar_cases > 0 なら
    実行する 類似度計算 dockerfile_keywords similar_cases
    記憶する similarity_score 結果
  終わり

  返す similarity_score
"""

    # プログラム読み込み
    vm.load_program(program)

    print("✓ Program loaded")
    print(f"  Labels: {list(vm.labels.keys())}")

    # 実行
    error_log = "Error: COPY failed: file not found FROM ubuntu:20.04 RUN apt-get update"
    result = vm.execute_label("docker_build_error_診断", error_log)

    print(f"\n✓ Execution completed")
    print(f"  Result: {result}")
    print(f"  Variables: {vm.variables}")
    print(f"  Cross Space objects: {len(vm.cross_space.objects)}")

    # 状態保存
    vm.save_state()
    print(f"\n✓ State saved to {vm.storage_path}")

    print("\n✅ .jcross VM test completed")


if __name__ == "__main__":
    test_jcross_vm()
