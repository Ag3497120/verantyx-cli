#!/usr/bin/env python3
"""
.jcross Japanese Parser (Stage 2.5)
完全日本語サポートのパーサー

日本語キーワード:
- 関数 (FUNCTION)
- 返す (RETURN)
- もし (IF)
- そうでなければ (ELSE)
- 各〜IN (FOR〜IN)
- 繰り返し (WHILE)
- 中断 (BREAK)
- 表示 (PRINT)
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class JCrossJapaneseParser:
    """完全日本語対応.jcrossパーサー"""

    def __init__(self):
        self.globals = {}
        self.functions = {}
        self.return_value = None
        self.has_returned = False
        self.break_flag = False
        self._init_builtins()

    def _init_builtins(self):
        """日本語組み込み関数を初期化"""
        import time
        import math

        # 日本語と英語の両方をサポート
        builtins_map = {
            # 日本語
            '長さ': lambda args: len(args[0]) if args else 0,
            '絶対値': lambda args: abs(args[0]) if args else 0,
            '現在時刻': lambda args: int(time.time()),
            '含む': lambda args: (args[1] in args[0]) if len(args) >= 2 else False,
            '大文字': lambda args: args[0].upper() if args and isinstance(args[0], str) else "",
            '小文字': lambda args: args[0].lower() if args and isinstance(args[0], str) else "",
            '分割': lambda args: args[0].split(args[1]) if len(args) >= 2 and isinstance(args[0], str) else [],
            '結合': lambda args: args[1].join(args[0]) if len(args) >= 2 and isinstance(args[0], list) else "",
            '最小': lambda args: min(args) if len(args) > 1 else (min(args[0]) if args and isinstance(args[0], list) else 0),
            '最大': lambda args: max(args) if len(args) > 1 else (max(args[0]) if args and isinstance(args[0], list) else 0),
            '合計': lambda args: sum(args[0]) if args and isinstance(args[0], list) else 0,
            '文字列': lambda args: str(args[0]) if args else "",
            '整数': lambda args: int(args[0]) if args else 0,
            '浮動小数': lambda args: float(args[0]) if args else 0.0,
            '平方根': lambda args: math.sqrt(args[0]) if args else 0,
            '四捨五入': lambda args: round(args[0], args[1]) if len(args) >= 2 else round(args[0]) if args else 0,

            # 英語（互換性のため）
            'LENGTH': lambda args: len(args[0]) if args else 0,
            'ABS': lambda args: abs(args[0]) if args else 0,
            'NOW': lambda args: int(time.time()),
            'CONTAINS': lambda args: (args[1] in args[0]) if len(args) >= 2 else False,
            'UPPER': lambda args: args[0].upper() if args and isinstance(args[0], str) else "",
            'LOWER': lambda args: args[0].lower() if args and isinstance(args[0], str) else "",
            'SPLIT': lambda args: args[0].split(args[1]) if len(args) >= 2 and isinstance(args[0], str) else [],
            'STR': lambda args: str(args[0]) if args else "",
            'INT': lambda args: int(args[0]) if args else 0,
            'FLOAT': lambda args: float(args[0]) if args else 0.0,
            'SQRT': lambda args: math.sqrt(args[0]) if args else 0,
            'ROUND': lambda args: round(args[0], args[1]) if len(args) >= 2 else round(args[0]) if args else 0,
        }

        self.builtins = builtins_map

    def execute_file(self, filepath: str) -> Any:
        """
        .jcrossファイルを実行

        Args:
            filepath: .jcrossファイルのパス

        Returns:
            実行結果
        """
        print(f"🚀 日本語.jcross実行: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        # 実行
        try:
            result = self.execute(source)
            print("✅ 実行完了")
            return result
        except Exception as e:
            print(f"❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            return None

    def execute(self, source: str) -> Any:
        """ソースコードを実行"""
        lines = source.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # コメントと空行をスキップ
            if not line or line.startswith('//'):
                i += 1
                continue

            # 文を実行
            i = self.execute_statement(lines, i)

            if self.has_returned:
                break

        return self.return_value

    def execute_statement(self, lines: List[str], start_idx: int) -> int:
        """文を実行し、次の行番号を返す"""
        line = lines[start_idx].strip()

        # 表示 (PRINT)
        if line.startswith('表示('):
            self.execute_print(line)
            return start_idx + 1

        # 関数定義
        if line.startswith('関数 '):
            return self.execute_function_def(lines, start_idx)

        # もし (IF)
        if line.startswith('もし '):
            return self.execute_if(lines, start_idx)

        # 繰り返し (WHILE true)
        if line == '繰り返し {':
            return self.execute_while(lines, start_idx)

        # 各〜IN (FOR IN)
        if line.startswith('各') and ' IN ' in line:
            return self.execute_for_in(lines, start_idx)

        # 返す (RETURN)
        if line.startswith('返す '):
            self.execute_return(line)
            return start_idx + 1

        # 中断 (BREAK)
        if line == '中断':
            self.break_flag = True
            return start_idx + 1

        # 代入
        if '=' in line and not any(op in line for op in ['==', '!=', '>=', '<=', '>',' <']):
            self.execute_assignment(line)
            return start_idx + 1

        # その他の式
        self.evaluate_expression(line)
        return start_idx + 1

    def execute_print(self, line: str):
        """表示文を実行"""
        # 表示(...)から内容を抽出
        match = re.match(r'表示\((.*)\)', line)
        if match:
            expr = match.group(1)
            value = self.evaluate_expression(expr)
            print(value)

    def execute_assignment(self, line: str):
        """代入を実行"""
        # フィールドアクセス対応: obj.field = value
        if '.' in line.split('=')[0]:
            parts = line.split('=', 1)
            lhs = parts[0].strip()
            rhs = parts[1].strip()

            # obj.field.subfield = value の形式に対応
            path_parts = lhs.split('.')
            obj_name = path_parts[0]

            if obj_name not in self.globals:
                return

            obj = self.globals[obj_name]

            # 最後のフィールド以外をたどる
            for field in path_parts[1:-1]:
                if isinstance(obj, dict) and field in obj:
                    obj = obj[field]
                else:
                    return

            # 最後のフィールドに値を設定
            last_field = path_parts[-1]
            value = self.evaluate_expression(rhs)

            if isinstance(obj, dict):
                obj[last_field] = value
        else:
            # 通常の代入
            parts = line.split('=', 1)
            var_name = parts[0].strip()
            value_expr = parts[1].strip()
            value = self.evaluate_expression(value_expr)
            self.globals[var_name] = value

    def execute_function_def(self, lines: List[str], start_idx: int) -> int:
        """関数定義を実行"""
        line = lines[start_idx].strip()

        # 関数 name(param1, param2) {
        match = re.match(r'関数\s+(\w+)\((.*?)\)\s*{', line)
        if not match:
            return start_idx + 1

        func_name = match.group(1)
        params_str = match.group(2)
        params = [p.strip() for p in params_str.split(',') if p.strip()]

        # 関数本体を見つける
        body_start = start_idx + 1
        body_end = self.find_matching_brace(lines, start_idx)

        # 関数を保存
        self.functions[func_name] = {
            'params': params,
            'body_lines': lines[body_start:body_end],
            'start': body_start,
            'end': body_end
        }

        return body_end + 1

    def execute_if(self, lines: List[str], start_idx: int) -> int:
        """もし文を実行"""
        line = lines[start_idx].strip()

        # もし condition {
        match = re.match(r'もし\s+(.+?)\s*{', line)
        if not match:
            return start_idx + 1

        condition = match.group(1)
        cond_value = self.evaluate_expression(condition)

        # ブロックを見つける
        if_end = self.find_matching_brace(lines, start_idx)

        # else句を探す
        else_start = None
        if if_end < len(lines) and lines[if_end].strip().startswith('} そうでなければ'):
            else_start = if_end
            # else句の終わりを見つける
            if lines[else_start].strip() == '} そうでなければ {':
                else_end = self.find_matching_brace(lines, else_start)
            else:
                else_end = else_start + 1

        if cond_value:
            # if句を実行
            i = start_idx + 1
            while i < if_end:
                if self.has_returned or self.break_flag:
                    break
                i = self.execute_statement(lines, i)
            return else_end + 1 if else_start else if_end + 1
        else:
            # else句があれば実行
            if else_start:
                i = else_start + 1
                while i < else_end:
                    if self.has_returned or self.break_flag:
                        break
                    i = self.execute_statement(lines, i)
                return else_end + 1
            return if_end + 1

    def execute_while(self, lines: List[str], start_idx: int) -> int:
        """繰り返し文を実行"""
        loop_end = self.find_matching_brace(lines, start_idx)

        while True:
            if self.has_returned:
                break

            # ブロックを実行
            i = start_idx + 1
            while i < loop_end:
                if self.has_returned or self.break_flag:
                    break
                i = self.execute_statement(lines, i)

            if self.break_flag:
                self.break_flag = False
                break

        return loop_end + 1

    def execute_for_in(self, lines: List[str], start_idx: int) -> int:
        """各〜IN文を実行"""
        line = lines[start_idx].strip()

        # 各item IN collection {
        match = re.match(r'各(\S+)\s+IN\s+(.+?)\s*{', line)
        if not match:
            return start_idx + 1

        item_var = match.group(1)
        collection_expr = match.group(2)
        collection = self.evaluate_expression(collection_expr)

        loop_end = self.find_matching_brace(lines, start_idx)

        if isinstance(collection, list):
            for item in collection:
                if self.has_returned or self.break_flag:
                    break

                self.globals[item_var] = item

                # ブロックを実行
                i = start_idx + 1
                while i < loop_end:
                    if self.has_returned or self.break_flag:
                        break
                    i = self.execute_statement(lines, i)

        if self.break_flag:
            self.break_flag = False

        return loop_end + 1

    def execute_return(self, line: str):
        """返す文を実行"""
        match = re.match(r'返す\s+(.+)', line)
        if match:
            expr = match.group(1)
            self.return_value = self.evaluate_expression(expr)
            self.has_returned = True

    def evaluate_expression(self, expr: str) -> Any:
        """式を評価"""
        expr = expr.strip()

        # 文字列リテラル
        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]

        # 数値リテラル
        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # 真偽値
        if expr == '真':
            return True
        if expr == '偽':
            return False

        # リストリテラル
        if expr.startswith('[') and expr.endswith(']'):
            return eval(expr)  # 簡易実装

        # 辞書リテラル
        if expr.startswith('{') and expr.endswith('}'):
            return eval(expr)  # 簡易実装

        # フィールドアクセス: obj.field
        if '.' in expr and not expr.startswith('"'):
            parts = expr.split('.')
            obj = self.globals.get(parts[0])

            for field in parts[1:]:
                if isinstance(obj, dict):
                    obj = obj.get(field)
                else:
                    break

            return obj

        # 関数呼び出し
        if '(' in expr and ')' in expr:
            return self.call_function(expr)

        # 二項演算
        for op in ['>=', '<=', '==', '!=', '>', '<', '+', '-', '*', '/']:
            if op in expr:
                return self.evaluate_binary_op(expr, op)

        # 変数参照
        return self.globals.get(expr, expr)

    def evaluate_binary_op(self, expr: str, op: str) -> Any:
        """二項演算を評価"""
        # 比較演算子を先に処理
        if op in ['>=', '<=', '==', '!=', '>', '<']:
            parts = expr.split(op, 1)
            if len(parts) != 2:
                return None

            left = self.evaluate_expression(parts[0].strip())
            right = self.evaluate_expression(parts[1].strip())

            if op == '>':
                return left > right
            elif op == '<':
                return left < right
            elif op == '>=':
                return left >= right
            elif op == '<=':
                return left <= right
            elif op == '==':
                return left == right
            elif op == '!=':
                return left != right

        # 算術演算子
        parts = expr.split(op, 1)
        if len(parts) != 2:
            return None

        left = self.evaluate_expression(parts[0].strip())
        right = self.evaluate_expression(parts[1].strip())

        # 文字列を数値に変換を試みる
        if isinstance(left, str):
            try:
                left = float(left) if '.' in left else int(left)
            except:
                pass

        if isinstance(right, str):
            try:
                right = float(right) if '.' in right else int(right)
            except:
                pass

        if op == '+':
            return left + right
        elif op == '-':
            return left - right
        elif op == '*':
            return left * right
        elif op == '/':
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left / right if right != 0 else 0
            return 0

        return None

    def call_function(self, expr: str) -> Any:
        """関数呼び出しを実行"""
        match = re.match(r'([\w]+)\((.*)\)', expr, re.DOTALL)
        if not match:
            return None

        func_name = match.group(1)
        args_str = match.group(2)

        # 引数を評価
        args = []
        if args_str.strip():
            # 簡易実装: カンマで分割（ネストを考慮しない）
            arg_parts = self.split_arguments(args_str)
            for arg in arg_parts:
                result = self.evaluate_expression(arg.strip())
                args.append(result)

    def split_arguments(self, args_str: str) -> List[str]:
        """関数引数を分割（ネストを考慮）"""
        parts = []
        current = ""
        depth = 0

        for char in args_str:
            if char in '([{':
                depth += 1
                current += char
            elif char in ')]}':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                parts.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            parts.append(current.strip())

        return parts

        # 組み込み関数
        if func_name in self.builtins:
            return self.builtins[func_name](args)

        # ユーザー定義関数
        if func_name in self.functions:
            func = self.functions[func_name]

            # パラメータをバインド
            old_globals = self.globals.copy()
            for i, param in enumerate(func['params']):
                if i < len(args):
                    self.globals[param] = args[i]

            # 関数本体を実行
            old_return = self.has_returned
            old_return_value = self.return_value
            self.has_returned = False
            self.return_value = None

            i = 0
            while i < len(func['body_lines']):
                if self.has_returned:
                    break
                i = self.execute_statement(func['body_lines'], i)

            result = self.return_value

            # 状態を復元
            self.has_returned = old_return
            self.return_value = old_return_value
            self.globals = old_globals

            return result

        return None

    def find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """対応する}を見つける"""
        depth = 1
        i = start_idx + 1

        while i < len(lines) and depth > 0:
            line = lines[i].strip()

            # コメントをスキップ
            if line.startswith('//'):
                i += 1
                continue

            depth += line.count('{')
            depth -= line.count('}')

            if depth == 0:
                return i

            i += 1

        return i


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使い方: python3 jcross_japanese_parser.py <file.jcross>")
        sys.exit(1)

    parser = JCrossJapaneseParser()
    parser.execute_file(sys.argv[1])
