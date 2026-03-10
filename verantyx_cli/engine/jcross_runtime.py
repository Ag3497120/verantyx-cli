#!/usr/bin/env python3
"""
JCross Runtime
JCross実行環境

Phase 5: 制御構文のサポート
- 定義する（関数定義）
- 繰り返す（ループ）
- もし（条件分岐）
- 返す（return）
"""

from typing import Dict, Any, List, Optional, Callable
import re


class JCrossFunction:
    """JCross関数"""

    def __init__(self, name: str, params: List[str], body: str):
        """
        Initialize

        Args:
            name: 関数名
            params: パラメータ名のリスト
            body: 関数本体
        """
        self.name = name
        self.params = params
        self.body = body

    def __repr__(self) -> str:
        return f"<JCrossFunction: {self.name}({', '.join(self.params)})>"


class JCrossRuntime:
    """
    JCross実行環境

    制御構文の実行をサポート
    """

    def __init__(self, globals_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize

        Args:
            globals_dict: グローバル変数辞書
        """
        self.globals = globals_dict if globals_dict is not None else {}
        self.functions: Dict[str, JCrossFunction] = {}
        self.locals_stack: List[Dict[str, Any]] = []

    def register_function(self, func: JCrossFunction):
        """
        関数を登録

        Args:
            func: JCrossFunction
        """
        self.functions[func.name] = func

    def parse_function_definition(self, code: str) -> Optional[JCrossFunction]:
        """
        「定義する」文をパースして関数を登録

        Args:
            code: 関数定義のコード

        Returns:
            JCrossFunction、またはNone
        """
        # 定義する 関数名 受け取る [パラメータ] = { 本体 }
        pattern = r'定義する\s+([^\s]+)\s+受け取る\s+\[([^\]]*)\]\s*=\s*\{(.+)\}'

        match = re.search(pattern, code, re.DOTALL)
        if not match:
            return None

        func_name = match.group(1).strip()
        params_str = match.group(2).strip()
        body = match.group(3).strip()

        # パラメータをパース
        params = []
        if params_str:
            params = [p.strip() for p in params_str.split(',')]

        func = JCrossFunction(func_name, params, body)
        self.register_function(func)

        return func

    def call_function(self, func_name: str, args: List[Any]) -> Any:
        """
        関数を呼び出し

        Args:
            func_name: 関数名
            args: 引数のリスト

        Returns:
            関数の返り値
        """
        if func_name not in self.functions:
            raise RuntimeError(f"Function not found: {func_name}")

        func = self.functions[func_name]

        if len(args) != len(func.params):
            raise RuntimeError(
                f"Argument count mismatch: {func_name} expects {len(func.params)}, got {len(args)}"
            )

        # ローカル変数スコープを作成
        local_vars = {}
        for param, arg in zip(func.params, args):
            local_vars[param] = arg

        self.locals_stack.append(local_vars)

        try:
            # 関数本体を実行
            result = self.execute_body(func.body)
            return result
        finally:
            # スコープを削除
            self.locals_stack.pop()

    def execute_body(self, body: str) -> Any:
        """
        関数本体を実行

        Args:
            body: 関数本体のコード

        Returns:
            返り値（返す文があれば）
        """
        # 簡易実装: 各文を順に実行
        lines = body.split('\n')

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # 返す文
            if line.startswith('返す '):
                value_expr = line[3:].strip()
                return self.evaluate_expression(value_expr)

            # もし文
            if line.startswith('もし '):
                result = self.execute_if_statement(line)
                if result is not None:
                    return result

            # 繰り返す文
            if line.startswith('繰り返す '):
                result = self.execute_loop_statement(line)
                if result is not None:
                    return result

            # 代入文
            if ' = ' in line:
                self.execute_assignment(line)

        return None

    def execute_if_statement(self, line: str) -> Any:
        """
        もし文を実行

        Args:
            line: もし文の行

        Returns:
            返り値（あれば）
        """
        # もし 条件:
        #   処理
        # 簡易実装: 単一行のみサポート

        pattern = r'もし\s+(.+):'
        match = re.match(pattern, line)

        if not match:
            return None

        condition_expr = match.group(1).strip()

        # 条件を評価
        condition_result = self.evaluate_expression(condition_expr)

        # Pythonの真偽値に変換
        if condition_result:
            # TODO: 次の行（インデントされた部分）を実行
            # 簡易実装では省略
            pass

        return None

    def execute_loop_statement(self, line: str) -> Any:
        """
        繰り返す文を実行

        Args:
            line: 繰り返す文の行

        Returns:
            返り値（あれば）
        """
        # 繰り返す 変数 in 範囲:
        # 簡易実装

        pattern = r'繰り返す\s+(\w+)\s+in\s+(.+):'
        match = re.match(pattern, line)

        if not match:
            return None

        var_name = match.group(1).strip()
        range_expr = match.group(2).strip()

        # 範囲を評価
        range_value = self.evaluate_expression(range_expr)

        # TODO: ループ本体を実行
        # 簡易実装では省略

        return None

    def execute_assignment(self, line: str):
        """
        代入文を実行

        Args:
            line: 代入文の行
        """
        parts = line.split(' = ', 1)
        if len(parts) != 2:
            return

        var_name = parts[0].strip()
        value_expr = parts[1].strip()

        # 値を評価
        value = self.evaluate_expression(value_expr)

        # ローカル変数に代入
        if self.locals_stack:
            self.locals_stack[-1][var_name] = value
        else:
            # グローバル変数に代入
            self.globals[var_name] = value

    def evaluate_expression(self, expr: str) -> Any:
        """
        式を評価

        Args:
            expr: 式の文字列

        Returns:
            評価結果
        """
        expr = expr.strip()

        # 数値
        try:
            if '.' in expr:
                return float(expr)
            else:
                return int(expr)
        except ValueError:
            pass

        # 文字列
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # 真偽値
        if expr == 'true' or expr == 'True':
            return True
        if expr == 'false' or expr == 'False':
            return False

        # 変数参照
        if expr in self.locals_stack[-1] if self.locals_stack else False:
            return self.locals_stack[-1][expr]

        if expr in self.globals:
            return self.globals[expr]

        # 関数呼び出し
        if '(' in expr and expr.endswith(')'):
            func_name = expr[:expr.index('(')].strip()
            args_str = expr[expr.index('(') + 1:-1].strip()

            # 引数をパース
            args = []
            if args_str:
                for arg_str in args_str.split(','):
                    args.append(self.evaluate_expression(arg_str.strip()))

            return self.call_function(func_name, args)

        # 演算子
        # 簡易実装: Pythonのevalを使用（安全性は低い）
        try:
            # ローカル変数とグローバル変数をマージ
            namespace = self.globals.copy()
            if self.locals_stack:
                namespace.update(self.locals_stack[-1])

            return eval(expr, {"__builtins__": {}}, namespace)
        except:
            pass

        # デフォルト: 文字列として返す
        return expr

    def __repr__(self) -> str:
        return f"<JCrossRuntime: {len(self.functions)} functions>"


def main():
    """テスト用メイン関数"""
    print("=" * 80)
    print("JCross実行環境テスト")
    print("=" * 80)
    print()

    # 実行環境を作成
    runtime = JCrossRuntime()

    # 簡単な関数を定義
    func_code = """
定義する 足し算 受け取る [a, b] = {
  返す a + b
}
"""

    print("関数定義:")
    print(func_code)

    # 関数をパース
    func = runtime.parse_function_definition(func_code)

    if func:
        print(f"✅ 関数登録成功: {func}")
        print()

        # 関数を呼び出し
        result = runtime.call_function("足し算", [10, 20])
        print(f"足し算(10, 20) = {result}")
    else:
        print("❌ 関数パース失敗")


if __name__ == "__main__":
    main()
