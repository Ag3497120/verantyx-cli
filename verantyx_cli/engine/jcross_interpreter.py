#!/usr/bin/env python3
"""
JCross Interpreter with Spatial Positioning
6次元空間配置機能付きJCrossインタープリタ

Features:
- 「生成する」のみサポート
- Cross構造をPython辞書/NumPy配列に変換
- 6D spatial positioning for data management
- Quality-based data placement (no deletion, only repositioning)
"""

import re
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import numpy as np


class JCrossParseError(Exception):
    """JCross parsing error"""
    pass


class SpatialPositionCalculator:
    """6次元空間内での位置計算とデータ配置を管理"""

    # UIノイズパターン（spatial_data_placement.jcross から）
    NOISE_PATTERNS = [
        "> ", "? for shortcuts",
        "Creating", "Swirling", "Baking", "Incubating", "Sautéing",
        "Brewing", "Crafting", "Mixing", "Preparing", "Cooking",
        "Distilling", "Fermenting", "Generating", "Processing",
        "⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷",  # スピナー文字
        "│", "─", "┤", "┬", "┴", "├", "┼",  # ボックス描画文字
        "\x1b[", "\r\n", "\\u",  # エスケープシーケンス
    ]

    def calculate_noise_ratio(self, content: str) -> float:
        """
        UIノイズの比率を計算

        Args:
            content: 分析対象のテキスト

        Returns:
            0.0 = ノイズなし, 1.0 = 100%ノイズ
        """
        if not content or len(content) == 0:
            return 1.0  # 空文字列は完全なノイズとみなす

        total_chars = len(content)
        noise_chars = 0

        for pattern in self.NOISE_PATTERNS:
            noise_chars += content.count(pattern) * len(pattern)

        noise_ratio = min(1.0, noise_chars / total_chars)
        return noise_ratio

    def calculate_quality_score(self, conversation: Dict[str, Any]) -> float:
        """
        会話の品質スコアを計算

        Args:
            conversation: 会話データ（role_pair を含む）

        Returns:
            0.0 = 低品質, 1.0 = 高品質
        """
        # アシスタントの応答を取得
        content = ""
        if "role_pair" in conversation:
            for msg in conversation["role_pair"]:
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    break
        elif "content" in conversation:
            content = conversation["content"]

        if not content:
            return 0.0

        # 長さスコア（500文字を満点とする）
        length_score = min(1.0, len(content) / 500.0)

        # ノイズスコア（ノイズが少ないほど高スコア）
        noise_score = 1.0 - self.calculate_noise_ratio(content)

        # 意味のある文字の比率（日本語、英数字、記号）
        meaningful_chars = len(re.findall(r'[a-zA-Z0-9\u3000-\u9fff！-～、。]', content))
        meaningful_score = meaningful_chars / len(content) if len(content) > 0 else 0.0

        # 総合品質スコア
        quality = (
            length_score * 0.3 +
            noise_score * 0.4 +
            meaningful_score * 0.3
        )

        return quality

    def calculate_6d_position(
        self,
        conversation: Dict[str, Any],
        current_time: Optional[datetime] = None
    ) -> Tuple[float, float, float, float, float, float]:
        """
        会話の6次元座標を計算

        Returns:
            (front_back, up_down, left_right, entity_relevance, intent_match, recency)
            各値は 0.0 ~ 1.0 の範囲
        """
        if current_time is None:
            current_time = datetime.now()

        # FRONT/BACK 軸: ノイズが少ないほどFRONT寄り
        noise_ratio = self.calculate_noise_ratio(
            self._get_content_from_conversation(conversation)
        )
        front_back = 1.0 - noise_ratio

        # UP/DOWN 軸: 品質が高いほどUP寄り
        quality_score = self.calculate_quality_score(conversation)
        up_down = quality_score

        # LEFT/RIGHT 軸: 新しいほどRIGHT寄り
        timestamp = conversation.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except:
                timestamp = current_time
        elif timestamp is None:
            timestamp = current_time

        age_days = (current_time - timestamp).total_seconds() / 86400.0
        recency = 1.0 / (1.0 + age_days)
        left_right = recency

        # 実体関連度と意図一致度は検索時に計算（デフォルト0.0）
        entity_relevance = 0.0
        intent_match = 0.0

        return (front_back, up_down, left_right, entity_relevance, intent_match, recency)

    def calculate_spatial_distance(
        self,
        conversation: Dict[str, Any],
        search_origin: Tuple[float, float, float, float, float, float]
    ) -> float:
        """
        6次元空間内でのユークリッド距離を計算

        Args:
            conversation: 会話データ
            search_origin: 検索原点の6次元座標

        Returns:
            距離（0.0に近いほど関連性が高い）
        """
        position = self.calculate_6d_position(conversation)

        # 6次元ユークリッド距離
        distance = math.sqrt(
            sum((p - o) ** 2 for p, o in zip(position, search_origin))
        )

        return distance

    def calculate_entity_relevance(
        self,
        conversation: Dict[str, Any],
        entity: str
    ) -> float:
        """
        会話と実体の関連度を計算

        Args:
            conversation: 会話データ
            entity: 検索実体（例: "openai", "claude max"）

        Returns:
            0.0 = 無関連, 1.0 = 完全一致
        """
        content = self._get_content_from_conversation(conversation)
        content_lower = content.lower()
        entity_lower = entity.lower()

        # 完全一致
        if entity_lower in content_lower:
            # 単語として完全一致しているか確認
            word_pattern = r'\b' + re.escape(entity_lower) + r'\b'
            if re.search(word_pattern, content_lower):
                return 1.0
            else:
                return 0.9  # 部分一致

        # 複合語の各単語が含まれているか
        entity_words = entity_lower.split()
        if len(entity_words) > 1:
            matches = sum(1 for word in entity_words if word in content_lower)
            return matches / len(entity_words)

        return 0.0

    def calculate_intent_match(
        self,
        conversation: Dict[str, Any],
        intent: str
    ) -> float:
        """
        会話と意図の一致度を計算

        Args:
            conversation: 会話データ
            intent: 意図（"definition", "explanation", etc.）

        Returns:
            0.0 = 不一致, 1.0 = 完全一致
        """
        content = self._get_content_from_conversation(conversation)

        # 意図に応じたキーワードパターン
        intent_patterns = {
            "definition": [r'とは', r'とは何', r'の意味', r'について', r'is', r'means'],
            "explanation": [r'説明', r'教えて', r'どう', r'explain', r'describe'],
            "how_to": [r'どうやって', r'方法', r'やり方', r'how to', r'how do'],
            "comparison": [r'違い', r'比較', r'difference', r'compare'],
        }

        patterns = intent_patterns.get(intent, [])
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return 1.0

        return 0.5  # デフォルト中間値

    def _get_content_from_conversation(self, conversation: Dict[str, Any]) -> str:
        """会話データから全テキストを抽出"""
        content_parts = []

        if "role_pair" in conversation:
            for msg in conversation["role_pair"]:
                content_parts.append(msg.get("content", ""))
        elif "content" in conversation:
            content_parts.append(conversation["content"])

        return " ".join(content_parts)


class SpatialDataManager:
    """6次元空間内でのデータ管理と検索を実行"""

    def __init__(self):
        self.calculator = SpatialPositionCalculator()

    def search_by_spatial_distance(
        self,
        user_question: str,
        entity: str,
        intent: str,
        conversations: List[Dict[str, Any]],
        max_distance: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        立体空間内の距離に基づいて最適な会話を検索

        Args:
            user_question: ユーザーの質問
            entity: 抽出された実体
            intent: 抽出された意図
            conversations: 検索対象の会話リスト
            max_distance: 許容最大距離

        Returns:
            最も近い会話データ、見つからない場合はNone
        """
        # 検索原点を設定
        # (FRONT, UP, RIGHT, 実体完全一致, 意図一致, 最新)
        search_origin = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)

        best_conversation = None
        min_distance = float('inf')

        for conv in conversations:
            # 空の応答はスキップ
            if self._is_empty_response(conv):
                continue

            # 実体関連度と意図一致度を計算
            entity_relevance = self.calculator.calculate_entity_relevance(conv, entity)
            intent_match = self.calculator.calculate_intent_match(conv, intent)

            # 検索原点を調整（実体と意図の次元を更新）
            adjusted_origin = (
                search_origin[0],  # FRONT
                search_origin[1],  # UP
                search_origin[2],  # RIGHT
                entity_relevance,   # 実体関連度
                intent_match,       # 意図一致度
                search_origin[5]    # 最新性
            )

            # 空間距離を計算
            distance = self.calculator.calculate_spatial_distance(conv, adjusted_origin)

            if distance < min_distance:
                min_distance = distance
                best_conversation = conv

        # 距離が閾値以内なら返す
        if min_distance <= max_distance:
            return {
                "conversation": best_conversation,
                "distance": min_distance,
                "spatial_score": 1.0 / (1.0 + min_distance)
            }

        return None

    def reposition_data_in_space(
        self,
        cross_memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用頻度や品質に基づいて、データを立体空間内で再配置

        重要: データは削除せず、ただ位置を変える

        Args:
            cross_memory: Cross構造のメモリ

        Returns:
            再配置されたメモリ
        """
        # 全会話を集める
        all_conversations = []

        if "FRONT" in cross_memory and "current_conversation" in cross_memory["FRONT"]:
            # 会話の配列として保存されている場合
            front_convs = cross_memory["FRONT"]["current_conversation"]
            if isinstance(front_convs, list):
                # 各会話がrole_pairを持っているか確認
                for i, conv in enumerate(front_convs):
                    if not isinstance(conv, dict):
                        continue
                    # 会話IDを保持
                    if "conversation_id" not in conv:
                        conv["conversation_id"] = f"conv_{i}"
                    all_conversations.append(conv)

        if "BACK" in cross_memory and "archived_conversations" in cross_memory["BACK"]:
            back_convs = cross_memory["BACK"]["archived_conversations"]
            if isinstance(back_convs, list):
                all_conversations.extend(back_convs)

        # 品質を計算
        for conv in all_conversations:
            conv["quality_score"] = self.calculator.calculate_quality_score(conv)
            conv["noise_ratio"] = self.calculator.calculate_noise_ratio(
                self.calculator._get_content_from_conversation(conv)
            )
            conv["access_count"] = conv.get("access_count", 0)

        # 再配置（削除しない）
        front_conversations = []
        back_conversations = []

        current_time = datetime.now()

        for conv in all_conversations:
            # タイムスタンプを取得
            timestamp = conv.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except:
                    timestamp = current_time
            elif timestamp is None:
                timestamp = current_time

            age_days = (current_time - timestamp).total_seconds() / 86400.0

            # FRONT配置条件（高品質、頻繁にアクセス、または最近のもの）
            if (
                conv["quality_score"] > 0.7 or
                conv["access_count"] > 5 or
                age_days < 7
            ):
                front_conversations.append(conv)
            else:
                back_conversations.append(conv)  # 削除しない、BACKに移動

        # メモリ構造を更新
        if "FRONT" not in cross_memory:
            cross_memory["FRONT"] = {}
        if "BACK" not in cross_memory:
            cross_memory["BACK"] = {}

        cross_memory["FRONT"]["active_conversations"] = front_conversations
        cross_memory["BACK"]["archived_conversations"] = back_conversations

        return cross_memory

    def add_new_conversation(
        self,
        cross_memory: Dict[str, Any],
        user_question: str,
        claude_response: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        新しい会話を追加（既存データを上書きしない）

        Args:
            cross_memory: Cross構造のメモリ
            user_question: ユーザーの質問
            claude_response: Claudeの応答
            timestamp: タイムスタンプ（省略時は現在時刻）

        Returns:
            更新されたメモリ
        """
        if timestamp is None:
            timestamp = datetime.now()

        # 新しい会話を作成
        new_conv = {
            "role_pair": [
                {
                    "role": "user",
                    "content": user_question,
                    "timestamp": timestamp.isoformat()
                },
                {
                    "role": "assistant",
                    "content": claude_response,
                    "timestamp": timestamp.isoformat()
                }
            ],
            "timestamp": timestamp.isoformat(),
            "access_count": 0
        }

        # 品質を計算
        quality_score = self.calculator.calculate_quality_score(new_conv)
        noise_ratio = self.calculator.calculate_noise_ratio(claude_response)

        new_conv["quality_score"] = quality_score
        new_conv["noise_ratio"] = noise_ratio

        # 品質に基づいて配置先を決定
        if "FRONT" not in cross_memory:
            cross_memory["FRONT"] = {"active_conversations": []}
        if "BACK" not in cross_memory:
            cross_memory["BACK"] = {"archived_conversations": []}

        if quality_score > 0.7:
            cross_memory["FRONT"]["active_conversations"].append(new_conv)
        else:
            cross_memory["BACK"]["archived_conversations"].append(new_conv)

        # 既存データは一切削除しない
        return cross_memory

    def _is_empty_response(self, conversation: Dict[str, Any]) -> bool:
        """応答が空または無意味かチェック"""
        content = self.calculator._get_content_from_conversation(conversation)

        # 空文字列
        if not content or len(content.strip()) == 0:
            return True

        # ノイズ比率が80%以上
        if self.calculator.calculate_noise_ratio(content) > 0.8:
            return True

        # 文字数が極端に少ない
        if len(content.strip()) < 10:
            return True

        return False


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
