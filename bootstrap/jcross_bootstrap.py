#!/usr/bin/env python3
"""
.jcross Bootstrap Interpreter
これだけがPython実装。これが動けば、後は全て.jcrossで実装可能。

目標: このファイルで jcross_interpreter.jcross を実行できるようにする
     → その後は.jcrossの世界（自己ホスティング）
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class JCrossBootstrap:
    """
    .jcrossブートストラップインタープリタ

    最小限の機能:
    - CROSS定義
    - FUNCTION定義
    - 基本的な制御構文（IF, FOR, WHILE）
    - 基本型（int, str, bool, list, dict）
    """

    def __init__(self):
        self.globals = {}
        self.crosses = {}
        self.functions = {}
        self.return_value = None
        self.has_returned = False
        self._init_builtins()

    def _init_builtins(self):
        """組み込み関数を初期化"""
        import time
        import math

        self.builtins = {
            'LENGTH': lambda args: len(args[0]) if args else 0,
            'ABS': lambda args: abs(args[0]) if args else 0,
            'NOW': lambda args: int(time.time()),
            'CONTAINS': lambda args: args[1] in args[0] if len(args) >= 2 else False,
            'UPPER': lambda args: args[0].upper() if args and isinstance(args[0], str) else "",
            'LOWER': lambda args: args[0].lower() if args and isinstance(args[0], str) else "",
            'SPLIT': lambda args: args[0].split(args[1]) if len(args) >= 2 and isinstance(args[0], str) else [],
            'JOIN': lambda args: args[1].join(args[0]) if len(args) >= 2 and isinstance(args[0], list) else "",
            'MIN': lambda args: min(args[0]) if args and isinstance(args[0], list) else None,
            'MAX': lambda args: max(args[0]) if args and isinstance(args[0], list) else None,
            'SUM': lambda args: sum(args[0]) if args and isinstance(args[0], list) else 0,
            'SORT': lambda args: sorted(args[0]) if args and isinstance(args[0], list) else [],
            'RANGE': lambda args: list(range(args[0])) if len(args) == 1 else list(range(args[0], args[1])) if len(args) == 2 else list(range(args[0], args[1], args[2])) if len(args) == 3 else [],
            'STR': lambda args: str(args[0]) if args else "",
            'INT': lambda args: int(args[0]) if args else 0,
            'FLOAT': lambda args: float(args[0]) if args else 0.0,
            'SQRT': lambda args: math.sqrt(args[0]) if args else 0,
            'ROUND': lambda args: round(args[0], args[1]) if len(args) >= 2 else round(args[0]) if args else 0,
        }

    def execute_file(self, filepath: str) -> Any:
        """
        .jcrossファイルを実行

        Args:
            filepath: .jcrossファイルのパス

        Returns:
            実行結果
        """
        print(f"🚀 Bootstrapping {filepath}...")

        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        # トークナイズ
        tokens = self.tokenize(source)
        print(f"   Tokenized: {len(tokens)} tokens")

        # パース
        ast = self.parse(tokens)
        print(f"   Parsed: {len(ast['body'])} nodes")

        # 実行
        result = self.execute(ast)
        print(f"✅ Bootstrap complete")

        return result

    def tokenize(self, source: str) -> List[tuple]:
        """
        トークナイズ

        Returns:
            [(type, value, position), ...]
        """
        tokens = []

        # パターン定義
        patterns = [
            ('COMMENT', r'//.*'),
            ('CROSS', r'\bCROSS\b'),
            ('FUNCTION', r'\bFUNCTION\b'),
            ('IF', r'\bIF\b'),
            ('ELSE', r'\bELSE\b'),
            ('FOR', r'\bFOR\b'),
            ('WHILE', r'\bWHILE\b'),
            ('RETURN', r'\bRETURN\b'),
            ('PRINT', r'\bPRINT\b'),
            ('IN', r'\bIN\b'),
            ('AND', r'\bAND\b'),
            ('OR', r'\bOR\b'),
            ('NOT', r'\bNOT\b'),
            ('TRUE', r'\btrue\b'),
            ('FALSE', r'\bfalse\b'),
            ('AXIS', r'\bAXIS\b'),
            ('UP', r'\bUP\b'),
            ('DOWN', r'\bDOWN\b'),
            ('LEFT', r'\bLEFT\b'),
            ('RIGHT', r'\bRIGHT\b'),
            ('FRONT', r'\bFRONT\b'),
            ('BACK', r'\bBACK\b'),
            ('STRING', r'"[^"]*"'),
            ('NUMBER', r'\d+\.?\d*'),
            ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),
            ('LBRACE', r'\{'),
            ('RBRACE', r'\}'),
            ('LPAREN', r'\('),
            ('RPAREN', r'\)'),
            ('LBRACKET', r'\['),
            ('RBRACKET', r'\]'),
            ('LESS_EQUAL', r'<='),
            ('GREATER_EQUAL', r'>='),
            ('EQUAL_EQUAL', r'=='),
            ('NOT_EQUAL', r'!='),
            ('LESS', r'<'),
            ('GREATER', r'>'),
            ('COLON', r':'),
            ('COMMA', r','),
            ('DOT', r'\.'),
            ('EQUALS', r'='),
            ('PLUS', r'\+'),
            ('MINUS', r'-'),
            ('MULTIPLY', r'\*'),
            ('DIVIDE', r'/'),
            ('MODULO', r'%'),
            ('WHITESPACE', r'\s+'),
        ]

        # 正規表現をコンパイル
        token_re = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in patterns)

        for match in re.finditer(token_re, source):
            kind = match.lastgroup
            value = match.group()
            position = match.start()

            # 空白とコメントはスキップ
            if kind in ('WHITESPACE', 'COMMENT'):
                continue

            # 文字列は引用符を除去
            if kind == 'STRING':
                value = value[1:-1]

            tokens.append((kind, value, position))

        return tokens

    def parse(self, tokens: List[tuple]) -> Dict:
        """
        パース

        Returns:
            AST (Abstract Syntax Tree)
        """
        ast = {'type': 'Program', 'body': []}
        pos = 0

        while pos < len(tokens):
            token_type, value, _ = tokens[pos]

            if token_type == 'CROSS':
                node, pos = self.parse_cross(tokens, pos)
                ast['body'].append(node)
            elif token_type == 'FUNCTION':
                node, pos = self.parse_function(tokens, pos)
                ast['body'].append(node)
            elif token_type == 'IF':
                node, pos = self.parse_if(tokens, pos)
                ast['body'].append(node)
            elif token_type == 'FOR':
                node, pos = self.parse_for(tokens, pos)
                ast['body'].append(node)
            elif token_type == 'WHILE':
                node, pos = self.parse_while(tokens, pos)
                ast['body'].append(node)
            elif token_type == 'PRINT':
                node, pos = self.parse_print(tokens, pos)
                ast['body'].append(node)
            elif token_type == 'IDENTIFIER':
                # 変数代入かチェック
                if pos + 1 < len(tokens) and tokens[pos + 1][0] == 'EQUALS':
                    node, pos = self.parse_assignment(tokens, pos)
                    ast['body'].append(node)
                else:
                    pos += 1
            else:
                pos += 1

        return ast

    def parse_cross(self, tokens: List[tuple], pos: int) -> tuple:
        """CROSS定義をパース"""
        pos += 1  # 'CROSS'をスキップ

        # CROSS名
        _, name, _ = tokens[pos]
        pos += 1

        # {
        pos += 1  # '{'をスキップ

        # 本体（簡易実装）
        axes = {}

        while tokens[pos][0] != 'RBRACE':
            if tokens[pos][0] == 'AXIS':
                axis_node, pos = self.parse_axis(tokens, pos)
                axes[axis_node['direction']] = axis_node
            else:
                pos += 1

        pos += 1  # '}'をスキップ

        return {
            'type': 'CrossDefinition',
            'name': name,
            'axes': axes
        }, pos

    def parse_axis(self, tokens: List[tuple], pos: int) -> tuple:
        """AXIS定義をパース"""
        pos += 1  # 'AXIS'をスキップ

        # 方向 (UP, DOWN, etc.)
        _, direction, _ = tokens[pos]
        pos += 1

        # {
        pos += 1

        # 本体（簡易実装: '}' まで読み飛ばし）
        depth = 1
        while depth > 0:
            if tokens[pos][0] == 'LBRACE':
                depth += 1
            elif tokens[pos][0] == 'RBRACE':
                depth -= 1
            pos += 1

        return {
            'type': 'AxisDefinition',
            'direction': direction
        }, pos

    def parse_function(self, tokens: List[tuple], pos: int) -> tuple:
        """FUNCTION定義をパース"""
        pos += 1  # 'FUNCTION'をスキップ

        # 関数名
        _, name, _ = tokens[pos]
        pos += 1

        # 引数リストをパース
        pos += 1  # '('をスキップ
        params = []
        while tokens[pos][0] != 'RPAREN':
            if tokens[pos][0] == 'IDENTIFIER':
                params.append(tokens[pos][1])
                pos += 1
            elif tokens[pos][0] == 'COMMA':
                pos += 1
            else:
                pos += 1
        pos += 1  # ')'をスキップ

        # 本体をパース
        pos += 1  # '{'をスキップ
        body = []
        depth = 1
        while depth > 0:
            if tokens[pos][0] == 'LBRACE':
                depth += 1
                pos += 1
            elif tokens[pos][0] == 'RBRACE':
                depth -= 1
                if depth == 0:
                    pos += 1
                    break
                pos += 1
            elif tokens[pos][0] == 'RETURN':
                node, pos = self.parse_return(tokens, pos)
                body.append(node)
            elif tokens[pos][0] == 'PRINT':
                node, pos = self.parse_print(tokens, pos)
                body.append(node)
            elif tokens[pos][0] == 'IF':
                node, pos = self.parse_if(tokens, pos)
                body.append(node)
            elif tokens[pos][0] == 'FOR':
                node, pos = self.parse_for(tokens, pos)
                body.append(node)
            elif tokens[pos][0] == 'WHILE':
                node, pos = self.parse_while(tokens, pos)
                body.append(node)
            elif tokens[pos][0] == 'IDENTIFIER' and pos + 1 < len(tokens) and tokens[pos + 1][0] == 'EQUALS':
                node, pos = self.parse_assignment(tokens, pos)
                body.append(node)
            else:
                pos += 1

        return {
            'type': 'FunctionDefinition',
            'name': name,
            'params': params,
            'body': body
        }, pos

    def parse_print(self, tokens: List[tuple], pos: int) -> tuple:
        """PRINT文をパース"""
        pos += 1  # 'PRINT'をスキップ

        pos += 1  # '('をスキップ

        # 引数を式としてパース
        expr_node, pos = self.parse_expression(tokens, pos)

        pos += 1  # ')'をスキップ

        return {
            'type': 'PrintStatement',
            'expression': expr_node
        }, pos

    def parse_assignment(self, tokens: List[tuple], pos: int) -> tuple:
        """変数代入をパース"""
        # 変数名
        _, var_name, _ = tokens[pos]
        pos += 1

        # =
        pos += 1

        # 値を評価
        value_node, pos = self.parse_expression(tokens, pos)

        return {
            'type': 'Assignment',
            'name': var_name,
            'value': value_node
        }, pos

    def parse_return(self, tokens: List[tuple], pos: int) -> tuple:
        """RETURN文をパース"""
        pos += 1  # 'RETURN'をスキップ

        # 返り値の式をパース
        value_node, pos = self.parse_expression(tokens, pos)

        return {
            'type': 'ReturnStatement',
            'value': value_node
        }, pos

    def parse_if(self, tokens: List[tuple], pos: int) -> tuple:
        """IF文をパース"""
        pos += 1  # 'IF'をスキップ

        # 条件式をパース
        condition_node, pos = self.parse_expression(tokens, pos)

        # '{'をスキップ
        pos += 1

        # then節をパース
        then_body = []
        depth = 1
        while depth > 0:
            if tokens[pos][0] == 'LBRACE':
                depth += 1
                pos += 1
            elif tokens[pos][0] == 'RBRACE':
                depth -= 1
                if depth == 0:
                    pos += 1  # '}'をスキップ
                    break
                pos += 1
            elif tokens[pos][0] == 'RETURN':
                node, pos = self.parse_return(tokens, pos)
                then_body.append(node)
            elif tokens[pos][0] == 'PRINT':
                node, pos = self.parse_print(tokens, pos)
                then_body.append(node)
            elif tokens[pos][0] == 'IDENTIFIER' and pos + 1 < len(tokens) and tokens[pos + 1][0] == 'EQUALS':
                node, pos = self.parse_assignment(tokens, pos)
                then_body.append(node)
            else:
                pos += 1

        # ELSE節があるかチェック
        else_body = []
        if pos < len(tokens) and tokens[pos][0] == 'ELSE':
            pos += 1  # 'ELSE'をスキップ
            pos += 1  # '{'をスキップ

            depth = 1
            while depth > 0:
                if tokens[pos][0] == 'LBRACE':
                    depth += 1
                    pos += 1
                elif tokens[pos][0] == 'RBRACE':
                    depth -= 1
                    if depth == 0:
                        pos += 1  # '}'をスキップ
                        break
                    pos += 1
                elif tokens[pos][0] == 'RETURN':
                    node, pos = self.parse_return(tokens, pos)
                    else_body.append(node)
                elif tokens[pos][0] == 'PRINT':
                    node, pos = self.parse_print(tokens, pos)
                    else_body.append(node)
                elif tokens[pos][0] == 'IDENTIFIER' and pos + 1 < len(tokens) and tokens[pos + 1][0] == 'EQUALS':
                    node, pos = self.parse_assignment(tokens, pos)
                    else_body.append(node)
                else:
                    pos += 1

        return {
            'type': 'IfStatement',
            'condition': condition_node,
            'then_body': then_body,
            'else_body': else_body
        }, pos

    def parse_for(self, tokens: List[tuple], pos: int) -> tuple:
        """FOR文をパース"""
        pos += 1  # 'FOR'をスキップ

        # イテレータ変数
        _, var_name, _ = tokens[pos]
        pos += 1

        # 'IN'をスキップ
        pos += 1

        # イテラブル（リストまたは変数）
        iterable_node, pos = self.parse_expression(tokens, pos)

        # '{'をスキップ
        pos += 1

        # ループ本体をパース
        body = []
        depth = 1
        while depth > 0:
            if tokens[pos][0] == 'LBRACE':
                depth += 1
                pos += 1
            elif tokens[pos][0] == 'RBRACE':
                depth -= 1
                if depth == 0:
                    pos += 1  # '}'をスキップ
                    break
                pos += 1
            elif tokens[pos][0] == 'PRINT':
                node, pos = self.parse_print(tokens, pos)
                body.append(node)
            elif tokens[pos][0] == 'IDENTIFIER' and pos + 1 < len(tokens) and tokens[pos + 1][0] == 'EQUALS':
                node, pos = self.parse_assignment(tokens, pos)
                body.append(node)
            else:
                pos += 1

        return {
            'type': 'ForStatement',
            'variable': var_name,
            'iterable': iterable_node,
            'body': body
        }, pos

    def parse_while(self, tokens: List[tuple], pos: int) -> tuple:
        """WHILE文をパース"""
        pos += 1  # 'WHILE'をスキップ

        # 条件式をパース
        condition_node, pos = self.parse_expression(tokens, pos)

        # '{'をスキップ
        pos += 1

        # ループ本体をパース
        body = []
        depth = 1
        while depth > 0:
            if tokens[pos][0] == 'LBRACE':
                depth += 1
                pos += 1
            elif tokens[pos][0] == 'RBRACE':
                depth -= 1
                if depth == 0:
                    pos += 1  # '}'をスキップ
                    break
                pos += 1
            elif tokens[pos][0] == 'PRINT':
                node, pos = self.parse_print(tokens, pos)
                body.append(node)
            elif tokens[pos][0] == 'IDENTIFIER' and pos + 1 < len(tokens) and tokens[pos + 1][0] == 'EQUALS':
                node, pos = self.parse_assignment(tokens, pos)
                body.append(node)
            else:
                pos += 1

        return {
            'type': 'WhileStatement',
            'condition': condition_node,
            'body': body
        }, pos

    def parse_expression(self, tokens: List[tuple], pos: int) -> tuple:
        """式をパース（数値、文字列、変数、演算）"""
        # 論理演算子のパース（OR）
        left_node, pos = self.parse_and_expression(tokens, pos)

        while pos < len(tokens) and tokens[pos][0] == 'OR':
            operator_type = tokens[pos][0]
            pos += 1
            right_node, pos = self.parse_and_expression(tokens, pos)
            left_node = {
                'type': 'BinaryOperation',
                'operator': operator_type,
                'left': left_node,
                'right': right_node
            }

        return left_node, pos

    def parse_and_expression(self, tokens: List[tuple], pos: int) -> tuple:
        """AND式をパース"""
        left_node, pos = self.parse_comparison(tokens, pos)

        while pos < len(tokens) and tokens[pos][0] == 'AND':
            operator_type = tokens[pos][0]
            pos += 1
            right_node, pos = self.parse_comparison(tokens, pos)
            left_node = {
                'type': 'BinaryOperation',
                'operator': operator_type,
                'left': left_node,
                'right': right_node
            }

        return left_node, pos

    def parse_comparison(self, tokens: List[tuple], pos: int) -> tuple:
        """比較演算子のパース"""
        left_node, pos = self.parse_arithmetic(tokens, pos)

        comparison_ops = ('LESS', 'GREATER', 'LESS_EQUAL', 'GREATER_EQUAL', 'EQUAL_EQUAL', 'NOT_EQUAL')
        if pos < len(tokens) and tokens[pos][0] in comparison_ops:
            operator_type = tokens[pos][0]
            pos += 1
            right_node, pos = self.parse_arithmetic(tokens, pos)
            left_node = {
                'type': 'BinaryOperation',
                'operator': operator_type,
                'left': left_node,
                'right': right_node
            }

        return left_node, pos

    def parse_arithmetic(self, tokens: List[tuple], pos: int) -> tuple:
        """算術演算子のパース"""
        left_node, pos = self.parse_unary(tokens, pos)

        arithmetic_ops = ('PLUS', 'MINUS', 'MULTIPLY', 'DIVIDE', 'MODULO')
        while pos < len(tokens) and tokens[pos][0] in arithmetic_ops:
            operator_type = tokens[pos][0]
            pos += 1
            right_node, pos = self.parse_unary(tokens, pos)
            left_node = {
                'type': 'BinaryOperation',
                'operator': operator_type,
                'left': left_node,
                'right': right_node
            }

        return left_node, pos

    def parse_unary(self, tokens: List[tuple], pos: int) -> tuple:
        """単項演算子のパース（NOT, -）"""
        if pos < len(tokens) and tokens[pos][0] in ('NOT', 'MINUS'):
            operator_type = tokens[pos][0]
            pos += 1
            operand, pos = self.parse_unary(tokens, pos)
            return {
                'type': 'UnaryOperation',
                'operator': operator_type,
                'operand': operand
            }, pos
        else:
            return self.parse_primary(tokens, pos)

    def parse_primary(self, tokens: List[tuple], pos: int) -> tuple:
        """基本式をパース（数値、文字列、変数）"""
        token_type, value, _ = tokens[pos]

        if token_type == 'NUMBER':
            # 数値リテラル
            return {
                'type': 'Literal',
                'value': int(value) if '.' not in value else float(value)
            }, pos + 1
        elif token_type == 'STRING':
            # 文字列リテラル
            return {
                'type': 'Literal',
                'value': value
            }, pos + 1
        elif token_type == 'TRUE':
            # Boolean true
            return {
                'type': 'Literal',
                'value': True
            }, pos + 1
        elif token_type == 'FALSE':
            # Boolean false
            return {
                'type': 'Literal',
                'value': False
            }, pos + 1
        elif token_type == 'IDENTIFIER':
            # 変数参照または関数呼び出し
            if pos + 1 < len(tokens) and tokens[pos + 1][0] == 'LPAREN':
                # 関数呼び出し
                func_name = value
                pos += 1  # IDENTIFIERをスキップ
                pos += 1  # '('をスキップ

                # 引数リストをパース
                args = []
                while tokens[pos][0] != 'RPAREN':
                    arg_node, pos = self.parse_expression(tokens, pos)
                    args.append(arg_node)
                    if tokens[pos][0] == 'COMMA':
                        pos += 1
                pos += 1  # ')'をスキップ

                return {
                    'type': 'FunctionCall',
                    'name': func_name,
                    'arguments': args
                }, pos
            else:
                # 変数参照（フィールドアクセスの可能性あり）
                base_node = {
                    'type': 'Identifier',
                    'name': value
                }
                pos += 1

                # ドット記法のチェック
                while pos < len(tokens) and tokens[pos][0] == 'DOT':
                    pos += 1  # '.' をスキップ
                    field_name = tokens[pos][1]
                    pos += 1
                    base_node = {
                        'type': 'FieldAccess',
                        'object': base_node,
                        'field': field_name
                    }

                return base_node, pos
        elif token_type == 'LPAREN':
            # 括弧でくくられた式
            pos += 1  # '(' をスキップ
            expr_node, pos = self.parse_expression(tokens, pos)
            pos += 1  # ')' をスキップ
            return expr_node, pos
        elif token_type == 'LBRACKET':
            # リストリテラル [1, 2, 3]
            pos += 1  # '[' をスキップ
            elements = []
            while tokens[pos][0] != 'RBRACKET':
                elem_node, pos = self.parse_expression(tokens, pos)
                elements.append(elem_node)
                if tokens[pos][0] == 'COMMA':
                    pos += 1  # ',' をスキップ
            pos += 1  # ']' をスキップ
            return {
                'type': 'ListLiteral',
                'elements': elements
            }, pos
        elif token_type == 'LBRACE':
            # 辞書リテラル {key: value, ...}
            pos += 1  # '{' をスキップ
            pairs = []
            while tokens[pos][0] != 'RBRACE':
                # キー（識別子または文字列）
                key_token_type, key_value, _ = tokens[pos]
                if key_token_type == 'IDENTIFIER':
                    key = key_value
                    pos += 1
                elif key_token_type == 'STRING':
                    key = key_value
                    pos += 1
                else:
                    pos += 1
                    continue

                # ':' をスキップ
                if tokens[pos][0] == 'COLON':
                    pos += 1

                # 値
                value_node, pos = self.parse_expression(tokens, pos)
                pairs.append({'key': key, 'value': value_node})

                # ',' をスキップ
                if tokens[pos][0] == 'COMMA':
                    pos += 1

            pos += 1  # '}' をスキップ
            return {
                'type': 'DictLiteral',
                'pairs': pairs
            }, pos
        else:
            # その他（エラー）
            return {'type': 'Unknown', 'value': value}, pos + 1

    def execute(self, ast: Dict) -> Any:
        """
        ASTを実行

        Args:
            ast: Abstract Syntax Tree

        Returns:
            実行結果
        """
        result = None

        for node in ast['body']:
            if node['type'] == 'CrossDefinition':
                self.crosses[node['name']] = node
                # CROSS構造を辞書として変数に保存
                cross_dict = {}
                for axis_name, axis_node in node['axes'].items():
                    cross_dict[axis_name] = axis_node
                self.globals[node['name']] = cross_dict
                print(f"✅ CROSS {node['name']} defined")

            elif node['type'] == 'FunctionDefinition':
                self.functions[node['name']] = node
                print(f"✅ FUNCTION {node['name']} defined")

            elif node['type'] == 'Assignment':
                # 変数代入を実行
                value = self.evaluate_expression(node['value'])
                self.globals[node['name']] = value
                print(f"✅ Assignment: {node['name']} = {value}")

            elif node['type'] == 'IfStatement':
                # IF文を実行
                condition_value = self.evaluate_expression(node['condition'])
                if condition_value:
                    # then節を実行
                    for then_node in node['then_body']:
                        self.execute_statement(then_node)
                elif node['else_body']:
                    # else節を実行
                    for else_node in node['else_body']:
                        self.execute_statement(else_node)

            elif node['type'] == 'ForStatement':
                # FOR文を実行
                iterable_value = self.evaluate_expression(node['iterable'])
                if iterable_value is not None:
                    for item in iterable_value:
                        # イテレータ変数に値を代入
                        self.globals[node['variable']] = item
                        # ループ本体を実行
                        for body_node in node['body']:
                            self.execute_statement(body_node)

            elif node['type'] == 'WhileStatement':
                # WHILE文を実行
                while True:
                    condition_value = self.evaluate_expression(node['condition'])
                    if not condition_value:
                        break
                    # ループ本体を実行
                    for body_node in node['body']:
                        self.execute_statement(body_node)

            elif node['type'] == 'PrintStatement':
                # 式を評価して出力
                value = self.evaluate_expression(node['expression'])
                print(value)

        return result

    def execute_statement(self, node: Dict) -> None:
        """単一の文を実行（IF文の中のネストした文用）"""
        if self.has_returned:
            return

        if node['type'] == 'Assignment':
            value = self.evaluate_expression(node['value'])
            self.globals[node['name']] = value
            print(f"✅ Assignment: {node['name']} = {value}")
        elif node['type'] == 'PrintStatement':
            value = self.evaluate_expression(node['expression'])
            print(value)
        elif node['type'] == 'IfStatement':
            condition_value = self.evaluate_expression(node['condition'])
            if condition_value:
                for then_node in node['then_body']:
                    self.execute_statement(then_node)
                    if self.has_returned:
                        break
            elif node['else_body']:
                for else_node in node['else_body']:
                    self.execute_statement(else_node)
                    if self.has_returned:
                        break
        elif node['type'] == 'ForStatement':
            iterable_value = self.evaluate_expression(node['iterable'])
            if iterable_value is not None:
                for item in iterable_value:
                    self.globals[node['variable']] = item
                    for body_node in node['body']:
                        self.execute_statement(body_node)
        elif node['type'] == 'WhileStatement':
            while True:
                condition_value = self.evaluate_expression(node['condition'])
                if not condition_value:
                    break
                for body_node in node['body']:
                    self.execute_statement(body_node)
        elif node['type'] == 'ReturnStatement':
            self.return_value = self.evaluate_expression(node['value'])
            self.has_returned = True

    def evaluate_expression(self, expr_node: Dict) -> Any:
        """
        式を評価

        Args:
            expr_node: 式のASTノード

        Returns:
            評価結果
        """
        if expr_node['type'] == 'Literal':
            # リテラル値
            return expr_node['value']
        elif expr_node['type'] == 'ListLiteral':
            # リストリテラル
            return [self.evaluate_expression(elem) for elem in expr_node['elements']]
        elif expr_node['type'] == 'DictLiteral':
            # 辞書リテラル
            result = {}
            for pair in expr_node['pairs']:
                key = pair['key']
                value = self.evaluate_expression(pair['value'])
                result[key] = value
            return result
        elif expr_node['type'] == 'FieldAccess':
            # フィールドアクセス (obj.field)
            obj = self.evaluate_expression(expr_node['object'])
            field = expr_node['field']
            if obj is None:
                print(f"❌ Error: Cannot access field '{field}' on None")
                return None
            if isinstance(obj, dict):
                if field in obj:
                    return obj[field]
                else:
                    print(f"❌ Error: Field '{field}' not found in dictionary")
                    return None
            else:
                print(f"❌ Error: Cannot access field '{field}' on non-dictionary type")
                return None
        elif expr_node['type'] == 'Identifier':
            # 変数参照
            var_name = expr_node['name']
            if var_name in self.globals:
                return self.globals[var_name]
            else:
                print(f"❌ Error: Undefined variable '{var_name}'")
                return None
        elif expr_node['type'] == 'FunctionCall':
            # 関数呼び出し
            func_name = expr_node['name']

            # 組み込み関数をチェック
            if func_name in self.builtins:
                # 引数を評価
                arg_values = [self.evaluate_expression(arg) for arg in expr_node['arguments']]
                # 組み込み関数を呼び出し
                try:
                    result = self.builtins[func_name](arg_values)
                    return result
                except Exception as e:
                    print(f"❌ Error in built-in function '{func_name}': {e}")
                    return None

            # ユーザー定義関数をチェック
            if func_name not in self.functions:
                print(f"❌ Error: Undefined function '{func_name}'")
                return None

            func_def = self.functions[func_name]

            # 引数を評価
            arg_values = [self.evaluate_expression(arg) for arg in expr_node['arguments']]

            # パラメータと引数をマッピング
            saved_globals = self.globals.copy()
            for param, arg_value in zip(func_def['params'], arg_values):
                self.globals[param] = arg_value

            # 関数本体を実行
            self.return_value = None
            self.has_returned = False
            for stmt in func_def['body']:
                self.execute_statement(stmt)
                if self.has_returned:
                    break

            # グローバル変数を復元
            result = self.return_value
            self.globals = saved_globals
            self.return_value = None
            self.has_returned = False

            return result
        elif expr_node['type'] == 'BinaryOperation':
            # 二項演算
            left_value = self.evaluate_expression(expr_node['left'])
            right_value = self.evaluate_expression(expr_node['right'])
            operator = expr_node['operator']

            if left_value is None or right_value is None:
                return None

            # 算術演算
            if operator == 'PLUS':
                return left_value + right_value
            elif operator == 'MINUS':
                return left_value - right_value
            elif operator == 'MULTIPLY':
                return left_value * right_value
            elif operator == 'DIVIDE':
                if right_value == 0:
                    print(f"❌ Error: Division by zero")
                    return None
                return left_value / right_value
            elif operator == 'MODULO':
                if right_value == 0:
                    print(f"❌ Error: Modulo by zero")
                    return None
                return left_value % right_value
            # 比較演算
            elif operator == 'LESS':
                return left_value < right_value
            elif operator == 'GREATER':
                return left_value > right_value
            elif operator == 'LESS_EQUAL':
                return left_value <= right_value
            elif operator == 'GREATER_EQUAL':
                return left_value >= right_value
            elif operator == 'EQUAL_EQUAL':
                return left_value == right_value
            elif operator == 'NOT_EQUAL':
                return left_value != right_value
            # 論理演算
            elif operator == 'AND':
                return left_value and right_value
            elif operator == 'OR':
                return left_value or right_value
            else:
                print(f"❌ Error: Unknown operator '{operator}'")
                return None
        elif expr_node['type'] == 'UnaryOperation':
            # 単項演算
            operand_value = self.evaluate_expression(expr_node['operand'])
            operator = expr_node['operator']

            if operand_value is None:
                return None

            if operator == 'NOT':
                return not operand_value
            elif operator == 'MINUS':
                return -operand_value
            else:
                print(f"❌ Error: Unknown unary operator '{operator}'")
                return None
        elif expr_node['type'] == 'Unknown':
            print(f"❌ Error: Unknown expression type")
            return None
        else:
            print(f"❌ Error: Unsupported expression type '{expr_node['type']}'")
            return None


def main():
    """メイン関数"""
    if len(sys.argv) < 2:
        print("Usage: python3 jcross_bootstrap.py <file.jcross>")
        sys.exit(1)

    filepath = sys.argv[1]

    if not Path(filepath).exists():
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    bootstrap = JCrossBootstrap()
    bootstrap.execute_file(filepath)


if __name__ == "__main__":
    main()
