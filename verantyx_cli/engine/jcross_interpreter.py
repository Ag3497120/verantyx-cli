#!/usr/bin/env python3
"""
JCross Minimal Interpreter
ミニマルJCrossインタープリタ

Phase 1: 最小限の.jcross実行
- 「生成する」のみサポート
- Cross構造をPython辞書/NumPy配列に変換
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np


class JCrossParseError(Exception):
    """JCross parsing error"""
    pass


class JCrossInterpreter:
    """
    ミニマルJCrossインタープリタ

    サポート:
    - 生成する (Cross構造の定義)
    - 基本的な辞書・リスト構造
    - コメント (#)
    """

    def __init__(self):
        """Initialize"""
        self.globals = {}
        self.debug = False

    def load_file(self, filepath: str) -> Dict[str, Any]:
        """
        .jcrossファイルを読み込んで実行

        Args:
            filepath: .jcrossファイルのパス

        Returns:
            グローバル変数の辞書
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()

        return self.execute(code)

    def execute(self, code: str) -> Dict[str, Any]:
        """
        JCrossコードを実行

        Args:
            code: JCrossコード

        Returns:
            グローバル変数の辞書
        """
        # 前処理: コメント除去、docstring除去
        code = self._preprocess(code)

        # 「生成する」文を抽出して実行
        self._execute_generate_statements(code)

        return self.globals

    def _preprocess(self, code: str) -> str:
        """
        前処理: コメント除去、docstring除去

        Args:
            code: 生のJCrossコード

        Returns:
            前処理済みコード
        """
        lines = []
        in_docstring = False

        for line in code.split('\n'):
            # Docstring開始/終了
            if line.strip().startswith('"""') or line.strip().startswith("'''"):
                if in_docstring:
                    in_docstring = False
                else:
                    in_docstring = True
                continue

            # Docstring内はスキップ
            if in_docstring:
                continue

            # コメント除去（#以降）
            # ただし文字列内の#は除外しない（簡易実装）
            if '#' in line:
                # 簡易: 文字列チェックせずに#以降を削除
                # TODO: 文字列内の#を保護
                line = line.split('#')[0]

            lines.append(line)

        return '\n'.join(lines)

    def _execute_generate_statements(self, code: str):
        """
        「生成する」文を抽出して実行

        Args:
            code: 前処理済みコード
        """
        # 「生成する」文を行ベースで抽出
        # ネストした{}に対応するため、手動でパース

        lines = code.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.startswith('生成する '):
                # 変数名を抽出
                match = re.match(r'生成する\s+([^\s=]+)\s*=\s*(.*)$', line)
                if not match:
                    i += 1
                    continue

                var_name = match.group(1).strip()
                first_value = match.group(2).strip()

                # 値が{で始まる場合、対応する}まで読み込む
                if first_value.startswith('{'):
                    value_lines = [first_value]
                    depth = first_value.count('{') - first_value.count('}')
                    i += 1

                    while depth > 0 and i < len(lines):
                        next_line = lines[i]
                        value_lines.append(next_line)
                        depth += next_line.count('{') - next_line.count('}')
                        i += 1

                    value_str = '\n'.join(value_lines)
                else:
                    value_str = first_value
                    i += 1

                if self.debug:
                    print(f"生成する {var_name} = ...")

                try:
                    # JSON風の構造をパース
                    value = self._parse_value(value_str)

                    # ネストした変数名に対応
                    self._set_nested_variable(var_name, value)

                except Exception as e:
                    if self.debug:
                        print(f"Warning: Failed to parse {var_name}: {e}")
                    # エラーは無視して続行
            else:
                i += 1

    def _parse_value(self, value_str: str) -> Any:
        """
        値の文字列をPythonオブジェクトにパース

        Args:
            value_str: 値の文字列

        Returns:
            Pythonオブジェクト（辞書、リスト、数値、文字列など）
        """
        value_str = value_str.strip()

        # 辞書
        if value_str.startswith('{') and value_str.endswith('}'):
            return self._parse_dict(value_str)

        # リスト
        if value_str.startswith('[') and value_str.endswith(']'):
            return self._parse_list(value_str)

        # 文字列（"..." または '...'）
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]

        # 真偽値
        if value_str == 'true' or value_str == 'True':
            return True
        if value_str == 'false' or value_str == 'False':
            return False
        if value_str == 'なし' or value_str == 'null':
            return None

        # 数値
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass

        # その他: そのまま文字列として返す
        return value_str

    def _parse_dict(self, dict_str: str) -> Dict[str, Any]:
        """
        辞書文字列をパース

        Args:
            dict_str: 辞書の文字列表現

        Returns:
            辞書
        """
        # {}を除去
        content = dict_str[1:-1].strip()

        if not content:
            return {}

        result = {}

        # キー:値 のペアを抽出
        # 簡易実装: ネストした{}や[]を考慮した分割
        pairs = self._split_dict_items(content)

        for pair in pairs:
            pair = pair.strip()
            if not pair:
                continue

            # キーと値を分割
            if ':' not in pair:
                continue

            # 最初の:で分割（値に:が含まれる可能性がある）
            key_str, value_str = pair.split(':', 1)

            key = key_str.strip().strip('"').strip("'")
            value = self._parse_value(value_str.strip())

            result[key] = value

        return result

    def _parse_list(self, list_str: str) -> List[Any]:
        """
        リスト文字列をパース

        Args:
            list_str: リストの文字列表現

        Returns:
            リスト
        """
        # []を除去
        content = list_str[1:-1].strip()

        if not content:
            return []

        result = []

        # 要素を抽出
        items = self._split_list_items(content)

        for item in items:
            item = item.strip()
            if not item:
                continue

            value = self._parse_value(item)
            result.append(value)

        return result

    def _split_dict_items(self, content: str) -> List[str]:
        """
        辞書の中身を項目ごとに分割（ネスト対応）

        Args:
            content: 辞書の中身

        Returns:
            項目のリスト
        """
        items = []
        current_item = ""
        depth = 0
        in_string = False
        string_char = None

        for char in content:
            # 文字列の開始/終了
            if char in ('"', "'") and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None

            # 文字列内ではネストを無視
            if in_string:
                current_item += char
                continue

            # ネストの深さを追跡
            if char in ('{', '['):
                depth += 1
            elif char in ('}', ']'):
                depth -= 1

            # トップレベルの,で分割
            if char == ',' and depth == 0:
                items.append(current_item)
                current_item = ""
            else:
                current_item += char

        # 最後の項目を追加
        if current_item.strip():
            items.append(current_item)

        return items

    def _split_list_items(self, content: str) -> List[str]:
        """
        リストの中身を項目ごとに分割（ネスト対応）

        Args:
            content: リストの中身

        Returns:
            項目のリスト
        """
        # 辞書と同じロジック
        return self._split_dict_items(content)

    def _set_nested_variable(self, var_name: str, value: Any):
        """
        ネストした変数名に値を設定

        例: DNA.ホメオスタシス閾値 → self.globals["DNA"]["ホメオスタシス閾値"]

        Args:
            var_name: 変数名（ドット区切り可）
            value: 値
        """
        parts = var_name.split('.')

        if len(parts) == 1:
            # 単純な変数
            self.globals[var_name] = value
        else:
            # ネストした変数
            current = self.globals

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = value

    def get(self, var_name: str, default: Any = None) -> Any:
        """
        変数の値を取得

        Args:
            var_name: 変数名（ドット区切り可）
            default: デフォルト値

        Returns:
            変数の値
        """
        parts = var_name.split('.')

        current = self.globals
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def dump_json(self, filepath: str):
        """
        グローバル変数をJSONファイルに保存

        Args:
            filepath: 保存先ファイルパス
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.globals, f, ensure_ascii=False, indent=2)

    def __repr__(self) -> str:
        return f"<JCrossInterpreter: {len(self.globals)} globals>"


def main():
    """テスト用メイン関数"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 jcross_interpreter.py <file.jcross>")
        sys.exit(1)

    filepath = sys.argv[1]

    print(f"📖 読み込み: {filepath}")
    print()

    interpreter = JCrossInterpreter()
    interpreter.debug = True

    try:
        result = interpreter.load_file(filepath)

        print()
        print("=" * 80)
        print("✅ 実行完了")
        print("=" * 80)
        print()

        # 主要な変数を表示
        for key in list(result.keys())[:10]:
            print(f"{key}: {type(result[key])}")

        print()
        print(f"総変数数: {len(result)}")

        # JSON出力
        output_file = Path(filepath).stem + "_output.json"
        interpreter.dump_json(output_file)
        print(f"📝 保存: {output_file}")

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
