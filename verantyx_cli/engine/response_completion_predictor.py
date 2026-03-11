#!/usr/bin/env python3
"""
Response Completion Predictor

Cross構造上でパズル推論を行い、文章がいつ完成するか予測

原理:
1. 届いたチャンクをCross構造上で組み立て
2. 文章構造を解析（穴埋め）
3. パズルのピースが全て埋まったら完成と判定
"""

from typing import List, Dict, Any, Optional
import re


class ResponseCompletionPredictor:
    """
    Cross構造を使った文章完成予測器

    文章がいつ終わるかを、waiting_for_input検出ではなく、
    Cross構造上でのパズル推論により予測
    """

    def __init__(self):
        # 文章の構造パターン
        self.structure_patterns = {
            'definition': {
                'required_pieces': ['subject', 'is_statement', 'explanation'],
                'optional_pieces': ['examples', 'comparison', 'technical_details']
            },
            'explanation': {
                'required_pieces': ['introduction', 'main_points', 'conclusion'],
                'optional_pieces': ['examples', 'references']
            },
            'comparison': {
                'required_pieces': ['entity_a', 'entity_b', 'comparison_points'],
                'optional_pieces': ['conclusion', 'recommendation']
            }
        }

        # 現在組み立て中の文章
        self.current_assembly = {
            'chunks': [],
            'detected_pieces': set(),
            'structure_type': None,
            'completion_score': 0.0
        }

    def add_chunk(self, chunk: str) -> Dict[str, Any]:
        """
        新しいチャンクを受信して組み立て

        Args:
            chunk: 受信したテキストチャンク

        Returns:
            {
                'is_complete': bool,
                'completion_score': float (0.0-1.0),
                'missing_pieces': List[str],
                'assembled_text': str
            }
        """
        # チャンクを追加
        self.current_assembly['chunks'].append(chunk)

        # 全体テキストを再構築
        full_text = ''.join(self.current_assembly['chunks'])

        # 文章タイプを検出（初回のみ）
        if not self.current_assembly['structure_type']:
            self.current_assembly['structure_type'] = self._detect_structure_type(full_text)

        # パズルのピースを検出
        detected_pieces = self._detect_pieces(full_text, self.current_assembly['structure_type'])
        self.current_assembly['detected_pieces'].update(detected_pieces)

        # 完成度を計算
        completion_score = self._calculate_completion_score(
            self.current_assembly['structure_type'],
            self.current_assembly['detected_pieces']
        )
        self.current_assembly['completion_score'] = completion_score

        # 欠けているピースを検出
        missing_pieces = self._get_missing_pieces(
            self.current_assembly['structure_type'],
            self.current_assembly['detected_pieces']
        )

        # 完成判定
        is_complete = self._is_complete(completion_score, missing_pieces, full_text)

        return {
            'is_complete': is_complete,
            'completion_score': completion_score,
            'missing_pieces': missing_pieces,
            'assembled_text': full_text,
            'detected_pieces': list(self.current_assembly['detected_pieces'])
        }

    def reset(self):
        """組み立て状態をリセット"""
        self.current_assembly = {
            'chunks': [],
            'detected_pieces': set(),
            'structure_type': None,
            'completion_score': 0.0
        }

    def _detect_structure_type(self, text: str) -> str:
        """文章の構造タイプを検出"""
        # 定義パターン（より柔軟に）
        if re.search(r'(.+?)(?:とは|には|は、|は )', text):
            return 'definition'

        # 比較パターン
        if '比較' in text or 'compared to' in text.lower() or 'vs' in text.lower():
            return 'comparison'

        # 説明パターン（デフォルト）
        return 'explanation'

    def _detect_pieces(self, text: str, structure_type: str) -> set:
        """文章のピースを検出"""
        pieces = set()

        if structure_type == 'definition':
            # 主語（Subject）- より柔軟に
            if re.search(r'^(.+?)(?:とは|には|は、|は )', text):
                pieces.add('subject')

            # is文（定義文）- より柔軟に
            if any(word in text for word in ['です', 'あります', 'います', 'is', 'means']):
                pieces.add('is_statement')

            # 説明（複数の文）- より柔軟に
            sentences = re.split(r'[。\n]', text)
            if len(sentences) >= 2:
                pieces.add('explanation')

            # 例示 - より柔軟に
            if any(word in text for word in ['例えば', 'example', '例：', '意味があります']):
                pieces.add('examples')

            # 比較
            if '比較' in text or 'compared' in text.lower():
                pieces.add('comparison')

            # 技術詳細（箇条書きや段落）- より柔軟に
            if re.search(r'[-•]|^\s*\d+\.|^  \d+\.|主な製品|製品：', text, re.MULTILINE):
                pieces.add('technical_details')

        elif structure_type == 'comparison':
            # エンティティA, B
            if re.search(r'(.+?)と(.+?)(?:の違い|を比較)', text):
                pieces.add('entity_a')
                pieces.add('entity_b')

            # 比較ポイント
            if '違い' in text or 'difference' in text.lower() or '一方' in text:
                pieces.add('comparison_points')

            # 結論
            if '結論' in text or '推奨' in text or 'conclusion' in text.lower():
                pieces.add('conclusion')

        elif structure_type == 'explanation':
            # イントロダクション
            sentences = re.split(r'[。\n]', text)
            if len(sentences) >= 1:
                pieces.add('introduction')

            # 主要ポイント（複数段落）
            paragraphs = text.split('\n\n')
            if len(paragraphs) >= 2:
                pieces.add('main_points')

            # 結論（最後の段落）
            if len(paragraphs) >= 3:
                pieces.add('conclusion')

        return pieces

    def _calculate_completion_score(self, structure_type: str, detected_pieces: set) -> float:
        """完成度スコアを計算（0.0-1.0）"""
        if not structure_type or structure_type not in self.structure_patterns:
            return 0.0

        pattern = self.structure_patterns[structure_type]
        required = set(pattern['required_pieces'])
        optional = set(pattern['optional_pieces'])

        # 必須ピースの充足率
        required_score = len(detected_pieces & required) / len(required) if required else 1.0

        # オプショナルピースのボーナス
        optional_score = len(detected_pieces & optional) / len(optional) if optional else 0.0

        # 総合スコア（必須80%、オプショナル20%）
        total_score = required_score * 0.8 + optional_score * 0.2

        return total_score

    def _get_missing_pieces(self, structure_type: str, detected_pieces: set) -> List[str]:
        """欠けているピースを取得"""
        if not structure_type or structure_type not in self.structure_patterns:
            return []

        pattern = self.structure_patterns[structure_type]
        required = set(pattern['required_pieces'])

        missing = required - detected_pieces

        return list(missing)

    def _is_complete(self, completion_score: float, missing_pieces: List[str], text: str) -> bool:
        """
        文章が完成したか判定

        複数の条件を総合的に判断：
        1. 完成度スコア >= 0.5（緩和）
        2. 必須ピースチェックは参考程度（厳しすぎるため）
        3. テキストが十分な長さ（100文字以上）
        4. 文末が適切（。や改行で終わる）
        """
        # 条件1: 完成度スコア（0.8 → 0.5 に緩和）
        if completion_score < 0.5:
            return False

        # 条件2: 必須ピースが全て揃っている（緩和 - 参考程度）
        # missing_pieces があっても、スコアが高ければOK
        # if missing_pieces:
        #     return False

        # 条件3: 十分な長さ
        if len(text.strip()) < 100:
            return False

        # 条件4: 文末チェック
        text_stripped = text.strip()
        if not text_stripped:
            return False

        # 適切な文末パターン
        proper_endings = [
            '。',
            '.',
            '）',
            ')',
            '」',
            '"',
            '！',
            '？',
        ]

        # 最後の文字が適切な終端か
        last_char = text_stripped[-1]
        if last_char not in proper_endings:
            # まだ続きがある可能性
            # ただし、改行が2つ以上連続していたら完成と判定
            if '\n\n' in text_stripped[-10:]:
                return True
            return False

        # 全ての条件を満たしたら完成
        return True


# テスト用
if __name__ == '__main__':
    predictor = ResponseCompletionPredictor()

    # シミュレーション: 段階的にチャンクを追加
    chunks = [
        "GitHubとは、",
        "Gitを使ったソースコードのバージョン管理とコラボレーションを行うためのWebサービスです。",
        "\n\n主な特徴\n",
        "- リポジトリホスティング\n",
        "- プルリクエスト\n",
        "- Issue管理\n",
        "\n\n技術的詳細\n",
        "Gitは分散型バージョン管理システムです。",
        "\n\n例えば、オープンソースプロジェクトで広く使われています。"
    ]

    print("=" * 80)
    print("Response Completion Prediction Simulation")
    print("=" * 80)

    for i, chunk in enumerate(chunks, 1):
        result = predictor.add_chunk(chunk)

        print(f"\n[Chunk {i}] Added: {chunk[:30]}...")
        print(f"  Completion: {result['completion_score']:.2%}")
        print(f"  Detected pieces: {result['detected_pieces']}")
        print(f"  Missing pieces: {result['missing_pieces']}")
        print(f"  Is complete? {'✅ YES' if result['is_complete'] else '❌ NO'}")

        if result['is_complete']:
            print(f"\n{'=' * 80}")
            print("✅ Response is COMPLETE!")
            print(f"{'=' * 80}")
            print(f"\nFinal text ({len(result['assembled_text'])} chars):")
            print(result['assembled_text'])
            break
