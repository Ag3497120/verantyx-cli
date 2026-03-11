#!/usr/bin/env python3
"""
Response Completion Processors

.jcrossファイルを実行するためのプロセッサ群
"""

import re
from typing import Any, Dict, List, Set, Optional


def CONTAINS(text: str, keywords: List[str]) -> bool:
    """テキストにキーワードが含まれるか"""
    return any(keyword in text.lower() for keyword in keywords)


def REGEX_MATCH(text: str, pattern: str) -> bool:
    """正規表現マッチング"""
    try:
        return bool(re.search(pattern, text, re.MULTILINE))
    except:
        return False


def ANY_IN(text: str, keywords: List[str]) -> bool:
    """いずれかのキーワードが含まれるか"""
    return any(keyword in text for keyword in keywords)


def SPLIT(text: str, pattern: str) -> List[str]:
    """文字列を分割"""
    try:
        return re.split(pattern, text)
    except:
        return [text]


def LENGTH(items) -> int:
    """長さを取得"""
    return len(items)


def STRIP(text: str) -> str:
    """前後の空白を削除"""
    return text.strip()


def EMPTY(items) -> bool:
    """空かどうか"""
    return len(items) == 0


def JOIN(items: List[str], separator: str = "") -> str:
    """リストを結合"""
    return separator.join(items)


def UNION(set1: Set, set2: Set) -> Set:
    """和集合"""
    return set1 | set2


def INTERSECTION(set1: Set, set2: Set) -> Set:
    """積集合"""
    return set1 & set2


def DIFFERENCE(set1: Set, set2: Set) -> Set:
    """差集合"""
    return set1 - set2


def ENDS_WITH(text: str, suffixes: List[str]) -> bool:
    """いずれかの接尾辞で終わるか"""
    return any(text.endswith(suffix) for suffix in suffixes)


class ResponseCompletionDetector:
    """
    Cross構造によるパズル推論を実行

    .jcrossファイルのロジックをPythonで実行
    """

    def __init__(self):
        # 文章構造のパターン（Cross構造）
        self.structure_patterns = {
            'definition': {
                'required': ['subject', 'is_statement', 'explanation'],
                'optional': ['examples', 'technical_details']
            },
            'explanation': {
                'required': ['introduction', 'main_points'],
                'optional': ['conclusion', 'examples']
            },
            'comparison': {
                'required': ['entity_a', 'entity_b', 'comparison_points'],
                'optional': ['conclusion']
            }
        }

        # 現在組み立て中の文章（Cross構造）
        self.current_assembly = {
            'chunks': [],
            'detected_pieces': set(),
            'structure_type': None,
            'completion_score': 0.0
        }

    def detect_structure_type(self, text: str) -> str:
        """文章タイプ検出（Cross推論）"""
        # 定義パターン
        if CONTAINS(text, ["とは", "には", "は、", "は "]):
            return 'definition'

        # 比較パターン
        if CONTAINS(text, ["比較", "compared to", "vs"]):
            return 'comparison'

        # デフォルト
        return 'explanation'

    def detect_pieces(self, text: str, structure_type: str) -> Set[str]:
        """ピース検出（Cross構造上のパターンマッチング）"""
        pieces = set()

        if structure_type == 'definition':
            # 主語
            if REGEX_MATCH(text, r'^(.+?)(?:とは|には|は、|は )'):
                pieces.add('subject')

            # is文
            if ANY_IN(text, ['です', 'あります', 'います', 'is', 'means']):
                pieces.add('is_statement')

            # 説明
            sentences = SPLIT(text, r'[。\n]')
            if LENGTH(sentences) >= 2:
                pieces.add('explanation')

            # 例示
            if ANY_IN(text, ['例えば', 'example', '例：', '意味があります', 'いくつかの']):
                pieces.add('examples')

            # 技術詳細
            if REGEX_MATCH(text, r'[-•]|^\s*\d+\.|主な|製品：|特徴：'):
                pieces.add('technical_details')

        elif structure_type == 'explanation':
            # イントロダクション
            sentences = SPLIT(text, r'[。\n]')
            if LENGTH(sentences) >= 1:
                pieces.add('introduction')

            # 主要ポイント
            if LENGTH(sentences) >= 3 or CONTAINS(text, ['主な', '特徴', '製品']):
                pieces.add('main_points')

            # 結論
            if LENGTH(sentences) >= 5 or ANY_IN(text, ['まとめ', 'conclusion', 'ですか？']):
                pieces.add('conclusion')

        elif structure_type == 'comparison':
            # エンティティA, B
            if REGEX_MATCH(text, r'(.+?)と(.+?)(?:の違い|を比較)'):
                pieces.add('entity_a')
                pieces.add('entity_b')

            # 比較ポイント
            if ANY_IN(text, ['違い', 'difference', '一方']):
                pieces.add('comparison_points')

            # 結論
            if ANY_IN(text, ['結論', '推奨', 'conclusion']):
                pieces.add('conclusion')

        return pieces

    def calculate_completion_score(self, structure_type: str, detected_pieces: Set[str]) -> float:
        """完成度スコア計算（Cross構造上で）"""
        if structure_type not in self.structure_patterns:
            return 0.0

        pattern = self.structure_patterns[structure_type]
        required = set(pattern['required'])
        optional = set(pattern['optional'])

        # 必須ピースの充足率
        required_fulfilled = INTERSECTION(detected_pieces, required)
        required_score = LENGTH(required_fulfilled) / LENGTH(required) if required else 1.0

        # オプショナルピースのボーナス
        optional_fulfilled = INTERSECTION(detected_pieces, optional)
        optional_score = LENGTH(optional_fulfilled) / LENGTH(optional) if optional else 0.0

        # 総合スコア（必須70%、オプショナル30%）
        total_score = required_score * 0.7 + optional_score * 0.3

        return total_score

    def is_complete(self, completion_score: float, text: str) -> bool:
        """
        完成判定（Cross推論の本質）

        .jcrossファイルの is_complete PATTERN を実行
        """
        # 条件1: スコアが40%以上
        if completion_score < 0.4:
            return False

        # 条件2: 十分な長さ（50文字以上）
        if LENGTH(STRIP(text)) < 50:
            return False

        # 条件3: スコアが80%以上なら文末チェック不要（完成とみなす）
        if completion_score >= 0.8:
            return True

        # 条件4: スコアが40-80%の場合のみ文末チェック
        text_stripped = STRIP(text)
        if EMPTY(text_stripped):
            return False

        # 適切な文末パターン（包括的）
        proper_endings = [
            # 日本語句読点
            '。', '、', '！', '？', '）', '】', '」', '』', '›', '…',
            # 英語句読点
            '.', '!', '?', ')', ']', '"', "'",
            # 日本語動詞/助動詞の終止形
            'す', 'た', 'ます', 'ました', 'です', 'でした',
            'る', 'れる', 'される', 'できる', 'ある', 'いる',
            'ん', 'の', 'か', 'ね', 'よ', 'わ', 'ぞ', 'さ'
        ]
        last_char = text_stripped[-1]

        if last_char in proper_endings:
            return True

        # 2文字以上の終わりパターン
        if LENGTH(text_stripped) >= 2:
            last_two = text_stripped[-2:]
            question_endings = ['か？', 'か。', 'か!', 'すか', 'ますか', 'でしょうか']
            if last_two in question_endings or any(text_stripped.endswith(q) for q in question_endings):
                return True

        # 改行が複数あれば完成と判定
        if '\n\n' in text_stripped[-20:]:
            return True

        # スコアが60%以上で、文が完結している形式なら完成
        if completion_score >= 0.6:
            if LENGTH(SPLIT(text_stripped, r'[。\n]')) >= 3:
                return True

        return False

    def add_chunk(self, chunk: str) -> Dict[str, Any]:
        """
        メインロジック: チャンク追加

        .jcrossファイルの add_chunk() FUNCTION を実行
        """
        # チャンクを追加
        self.current_assembly['chunks'].append(chunk)

        # 全体テキストを再構築
        full_text = JOIN(self.current_assembly['chunks'], '')

        # 文章タイプを検出（初回のみ）
        if self.current_assembly['structure_type'] is None:
            self.current_assembly['structure_type'] = self.detect_structure_type(full_text)

        # パズルのピースを検出
        new_pieces = self.detect_pieces(full_text, self.current_assembly['structure_type'])
        self.current_assembly['detected_pieces'] = UNION(
            self.current_assembly['detected_pieces'],
            new_pieces
        )

        # 完成度を計算
        completion_score = self.calculate_completion_score(
            self.current_assembly['structure_type'],
            self.current_assembly['detected_pieces']
        )
        self.current_assembly['completion_score'] = completion_score

        # 欠けているピースを検出
        pattern = self.structure_patterns[self.current_assembly['structure_type']]
        required = set(pattern['required'])
        missing_pieces = DIFFERENCE(required, self.current_assembly['detected_pieces'])

        # 完成判定
        is_complete_result = self.is_complete(completion_score, full_text)

        return {
            'is_complete': is_complete_result,
            'completion_score': completion_score,
            'missing_pieces': list(missing_pieces),
            'assembled_text': full_text,
            'detected_pieces': list(self.current_assembly['detected_pieces']),
            'structure_type': self.current_assembly['structure_type']
        }

    def reset(self):
        """リセット"""
        self.current_assembly = {
            'chunks': [],
            'detected_pieces': set(),
            'structure_type': None,
            'completion_score': 0.0
        }
