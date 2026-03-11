#!/usr/bin/env python3
"""
Knowledge Learner - Claude Codeの一般知識応答を学習

エージェント操作だけでなく、説明・概念・推論なども学習：
- 質問への回答パターン
- 概念説明
- 技術知識
- 推論プロセス
- アドバイス・提案
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict


class KnowledgeLearner:
    """
    Claude Codeの一般知識応答を学習

    学習内容:
    - 質問への回答パターン
    - 概念説明（技術用語、アーキテクチャなど）
    - 技術知識（ベストプラクティス、設計原則など）
    - 推論プロセス（問題分析、意思決定など）
    - アドバイス・提案（改善案、代替案など）
    """

    def __init__(self, cross_file: Path):
        """
        Args:
            cross_file: Cross構造ファイル
        """
        self.cross_file = cross_file
        self.cross_memory = self._load_cross_memory()

        # 学習した知識
        self.learned_knowledge = {
            'qa_patterns': {},           # Q&Aパターン
            'concepts': {},              # 概念説明
            'technical_knowledge': {},   # 技術知識
            'reasoning_patterns': [],    # 推論パターン
            'advice_patterns': {},       # アドバイスパターン
            'explanations': {},          # 説明パターン
        }

        self._extract_knowledge()

    def _load_cross_memory(self) -> Dict:
        """Cross構造を読み込む"""
        if not self.cross_file.exists():
            return {'axes': {}}

        try:
            with open(self.cross_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {'axes': {}}

    def _extract_knowledge(self):
        """Cross構造から一般知識を抽出"""
        axes = self.cross_memory.get('axes', {})

        # 会話から学習
        self._learn_qa_patterns(axes.get('FRONT', {}), axes.get('UP', {}), axes.get('DOWN', {}))

        # 概念・説明を学習
        self._learn_concepts(axes.get('DOWN', {}))

        # 技術知識を学習
        self._learn_technical_knowledge(axes.get('DOWN', {}))

        # 推論パターンを学習
        self._learn_reasoning_patterns(axes.get('FRONT', {}))

        # アドバイスパターンを学習
        self._learn_advice_patterns(axes.get('DOWN', {}))

    def _learn_qa_patterns(self, front_axis: Dict, up_axis: Dict, down_axis: Dict):
        """
        質問への回答パターンを学習

        ユーザーの質問とClaudeの応答をペアで学習
        """
        user_inputs = up_axis.get('user_inputs', [])
        claude_responses = down_axis.get('claude_responses', [])

        for i, user_input in enumerate(user_inputs):
            if i >= len(claude_responses):
                break

            if not isinstance(user_input, str) or not isinstance(claude_responses[i], str):
                continue

            # コンテキストマーカーを抽出・除去
            cleaned_input, context_info = self._extract_context_marker(user_input)

            # 質問タイプを分類
            question_type = self._classify_question(cleaned_input)

            if question_type != 'unknown':
                # キーワード抽出
                keywords = self._extract_keywords(cleaned_input)

                # コンテキストを考慮したパターンキー
                if context_info:
                    # コンテキストIDを含める（同じトピックの会話をグループ化）
                    pattern_key = f"{question_type}:{context_info['topic']}:{','.join(keywords[:3])}"
                else:
                    pattern_key = f"{question_type}:{','.join(keywords[:3])}"

                if pattern_key not in self.learned_knowledge['qa_patterns']:
                    self.learned_knowledge['qa_patterns'][pattern_key] = []

                qa_entry = {
                    'question': cleaned_input[:200],
                    'response': claude_responses[i][:1000],
                    'keywords': keywords,
                    'learned_at': datetime.now().isoformat()
                }

                # コンテキスト情報を保存
                if context_info:
                    qa_entry['context'] = context_info

                self.learned_knowledge['qa_patterns'][pattern_key].append(qa_entry)

    def _classify_question(self, text: str) -> str:
        """質問タイプを分類"""
        lower = text.lower()

        # What系: 定義・説明を求める（「〜とは」パターンを追加）
        if any(w in lower for w in ['what is', 'what are', 'what does', 'なに', 'なんで', '何']) or \
           'とは' in text or 'って何' in text or 'って' in text:
            return 'definition'

        # How系: 方法・手順を求める
        elif any(w in lower for w in ['how to', 'how do', 'how can', 'どうやって', 'どう', '方法']):
            return 'how_to'

        # Why系: 理由・原因を求める
        elif any(w in lower for w in ['why', 'why does', 'なぜ', '理由', '原因']):
            return 'reasoning'

        # Which/When/Where系: 比較・選択を求める
        elif any(w in lower for w in ['which', 'when', 'where', 'どれ', 'いつ', 'どこ']):
            return 'comparison'

        # Can/Should系: 判断・アドバイスを求める
        elif any(w in lower for w in ['can i', 'should i', 'できる', 'すべき', '可能']):
            return 'advice'

        # Explain系: 詳細説明を求める
        elif any(w in lower for w in ['explain', 'describe', 'tell me about', '説明', '教えて']):
            return 'explanation'

        else:
            return 'unknown'

    def _extract_context_marker(self, text: str) -> Tuple[str, Optional[Dict[str, str]]]:
        """
        コンテキストマーカーを抽出して除去

        Args:
            text: ユーザー入力（コンテキストマーカーを含む可能性）

        Returns:
            (cleaned_text, context_info)
        """
        # パターン: [CTX:ctx_id|TOPIC:topic_name] actual_message
        import re
        pattern = r'\[CTX:([^\|]+)\|TOPIC:([^\]]+)\]\s*'
        match = re.match(pattern, text)

        if match:
            context_id = match.group(1)
            topic = match.group(2)
            cleaned_text = re.sub(pattern, '', text).strip()

            context_info = {
                'context_id': context_id,
                'topic': topic
            }

            return cleaned_text, context_info

        return text, None

    def _extract_keywords(self, text: str) -> List[str]:
        """テキストからキーワードを抽出"""
        # 記号を除去
        cleaned = re.sub(r'[^\w\s]', ' ', text)

        # 単語に分割
        words = cleaned.lower().split()

        # ストップワードを除外
        stop_words = {
            'the', 'a', 'an', 'in', 'on', 'at', 'for', 'to', 'of', 'and', 'or',
            'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'what', 'how', 'why', 'when', 'where', 'which',
            'の', 'を', 'に', 'が', 'は', 'で', 'と', 'も', 'から', 'まで'
        }

        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords[:10]  # 最大10個

    def _learn_concepts(self, down_axis: Dict):
        """
        概念説明を学習

        技術用語やアーキテクチャの説明を抽出
        """
        responses = down_axis.get('claude_responses', [])

        for response in responses:
            if not isinstance(response, str):
                continue

            # 「〜とは」「〜is」などの定義パターンを検出
            definition_patterns = [
                r'(\w+)\s+(?:is|are|means?|refers? to)\s+(.+?)(?:\.|$)',
                r'(\w+)\s*[:：]\s*(.+?)(?:\.|$)',
                r'(\w+)とは(.+?)(?:。|$)',
            ]

            for pattern in definition_patterns:
                matches = re.findall(pattern, response, re.MULTILINE | re.IGNORECASE)

                for term, definition in matches:
                    term = term.strip()
                    definition = definition.strip()[:500]

                    if len(term) > 2 and len(definition) > 10:
                        if term not in self.learned_knowledge['concepts']:
                            self.learned_knowledge['concepts'][term] = []

                        self.learned_knowledge['concepts'][term].append({
                            'definition': definition,
                            'learned_at': datetime.now().isoformat()
                        })

    def _learn_technical_knowledge(self, down_axis: Dict):
        """
        技術知識を学習

        ベストプラクティス、設計原則、推奨事項など
        """
        responses = down_axis.get('claude_responses', [])

        for response in responses:
            if not isinstance(response, str):
                continue

            # ベストプラクティスパターン
            if any(word in response.lower() for word in ['best practice', 'recommended', 'should', 'ベストプラクティス', '推奨', 'すべき']):
                category = 'best_practices'

            # 設計原則パターン
            elif any(word in response.lower() for word in ['principle', 'pattern', 'architecture', '原則', 'パターン', 'アーキテクチャ']):
                category = 'design_principles'

            # 注意事項パターン
            elif any(word in response.lower() for word in ['warning', 'caution', 'note', 'important', '注意', '重要']):
                category = 'warnings'

            else:
                continue

            if category not in self.learned_knowledge['technical_knowledge']:
                self.learned_knowledge['technical_knowledge'][category] = []

            self.learned_knowledge['technical_knowledge'][category].append({
                'content': response[:500],
                'learned_at': datetime.now().isoformat()
            })

    def _learn_reasoning_patterns(self, front_axis: Dict):
        """
        推論パターンを学習

        問題分析、意思決定のプロセス
        """
        conversations = front_axis.get('current_conversation', [])

        for conv in conversations:
            if not isinstance(conv, dict):
                continue

            role = conv.get('role', '')
            content = str(conv.get('content', ''))

            if role != 'assistant':
                continue

            # 推論キーワード
            reasoning_keywords = [
                'because', 'therefore', 'however', 'although', 'since',
                'なぜなら', 'したがって', 'しかし', 'ただし', 'そのため',
                'first', 'second', 'finally', 'then',
                'まず', '次に', '最後に', 'そして'
            ]

            if any(keyword in content.lower() for keyword in reasoning_keywords):
                self.learned_knowledge['reasoning_patterns'].append({
                    'content': content[:500],
                    'learned_at': datetime.now().isoformat()
                })

    def _learn_advice_patterns(self, down_axis: Dict):
        """
        アドバイスパターンを学習

        改善案、代替案、提案など
        """
        responses = down_axis.get('claude_responses', [])

        for response in responses:
            if not isinstance(response, str):
                continue

            # アドバイスキーワード
            advice_keywords = [
                'suggest', 'recommend', 'consider', 'try', 'you could', 'you should',
                '提案', '推奨', '検討', '試す', 'できる', 'すべき'
            ]

            has_advice = any(keyword in response.lower() for keyword in advice_keywords)

            if has_advice:
                # カテゴリ分類
                if 'improve' in response.lower() or '改善' in response:
                    category = 'improvements'
                elif 'alternative' in response.lower() or '代替' in response:
                    category = 'alternatives'
                elif 'next step' in response.lower() or '次' in response:
                    category = 'next_steps'
                else:
                    category = 'general'

                if category not in self.learned_knowledge['advice_patterns']:
                    self.learned_knowledge['advice_patterns'][category] = []

                self.learned_knowledge['advice_patterns'][category].append({
                    'content': response[:500],
                    'learned_at': datetime.now().isoformat()
                })

    def get_knowledge_summary(self) -> Dict[str, Any]:
        """学習した知識のサマリーを取得"""
        return {
            'qa_patterns_count': len(self.learned_knowledge['qa_patterns']),
            'qa_types': list(set([
                k.split(':')[0] for k in self.learned_knowledge['qa_patterns'].keys()
            ])),
            'concepts_count': len(self.learned_knowledge['concepts']),
            'top_concepts': list(self.learned_knowledge['concepts'].keys())[:10],
            'technical_knowledge_count': sum(
                len(items) for items in self.learned_knowledge['technical_knowledge'].values()
            ),
            'technical_categories': list(self.learned_knowledge['technical_knowledge'].keys()),
            'reasoning_patterns_count': len(self.learned_knowledge['reasoning_patterns']),
            'advice_patterns_count': sum(
                len(items) for items in self.learned_knowledge['advice_patterns'].values()
            ),
            'advice_categories': list(self.learned_knowledge['advice_patterns'].keys()),
        }

    def find_similar_qa(self, user_question: str) -> Optional[str]:
        """
        類似Q&Aを検索

        Args:
            user_question: ユーザーの質問

        Returns:
            類似する過去の応答、見つからなければNone
        """
        question_type = self._classify_question(user_question)
        keywords = self._extract_keywords(user_question)

        best_match = None
        best_score = 0

        for pattern_key, qa_list in self.learned_knowledge['qa_patterns'].items():
            stored_type = pattern_key.split(':')[0]

            # タイプが一致するか
            if stored_type != question_type:
                continue

            for qa in qa_list:
                # キーワードマッチング
                stored_keywords = set(qa['keywords'])
                query_keywords = set(keywords)

                if not query_keywords:
                    continue

                # Jaccard類似度
                intersection = stored_keywords & query_keywords
                union = stored_keywords | query_keywords

                score = len(intersection) / len(union) if len(union) > 0 else 0

                if score > best_score:
                    best_score = score
                    best_match = qa['response']

        # 類似度が30%以上なら採用
        if best_score > 0.3:
            return best_match

        return None

    def get_concept_explanation(self, term: str) -> Optional[str]:
        """
        概念の説明を取得

        Args:
            term: 用語

        Returns:
            説明、見つからなければNone
        """
        # 完全一致
        if term in self.learned_knowledge['concepts']:
            explanations = self.learned_knowledge['concepts'][term]
            if explanations:
                return explanations[-1]['definition']  # 最新の説明

        # 部分一致
        term_lower = term.lower()
        for concept_term, explanations in self.learned_knowledge['concepts'].items():
            if term_lower in concept_term.lower() or concept_term.lower() in term_lower:
                if explanations:
                    return explanations[-1]['definition']

        return None

    def get_technical_knowledge(self, category: str) -> List[str]:
        """
        技術知識を取得

        Args:
            category: カテゴリ ('best_practices', 'design_principles', 'warnings')

        Returns:
            技術知識のリスト
        """
        items = self.learned_knowledge['technical_knowledge'].get(category, [])
        return [item['content'] for item in items[:5]]  # 最大5個

    def get_advice(self, category: str = 'general') -> List[str]:
        """
        アドバイスを取得

        Args:
            category: カテゴリ ('improvements', 'alternatives', 'next_steps', 'general')

        Returns:
            アドバイスのリスト
        """
        items = self.learned_knowledge['advice_patterns'].get(category, [])
        return [item['content'] for item in items[:3]]  # 最大3個

    def get_reasoning_examples(self, count: int = 3) -> List[str]:
        """
        推論パターンの例を取得

        Args:
            count: 取得する数

        Returns:
            推論パターンのリスト
        """
        patterns = self.learned_knowledge['reasoning_patterns'][-count:]
        return [p['content'] for p in patterns]


def test_knowledge_learner():
    """知識学習のテスト"""
    print("\n" + "=" * 70)
    print("  📚 Knowledge Learner Test")
    print("=" * 70)
    print()

    cross_file = Path(".verantyx/conversation.cross.json")

    if not cross_file.exists():
        print(f"⚠️  No Cross file found: {cross_file}")
        return

    learner = KnowledgeLearner(cross_file)

    print("📊 Learned Knowledge Summary:")
    summary = learner.get_knowledge_summary()

    print(f"\n  Q&A Patterns: {summary['qa_patterns_count']}")
    if summary['qa_types']:
        print(f"  Question types: {', '.join(summary['qa_types'])}")

    print(f"\n  Concepts: {summary['concepts_count']}")
    if summary['top_concepts']:
        print(f"  Top concepts: {', '.join(summary['top_concepts'][:5])}")

    print(f"\n  Technical Knowledge: {summary['technical_knowledge_count']}")
    if summary['technical_categories']:
        print(f"  Categories: {', '.join(summary['technical_categories'])}")

    print(f"\n  Reasoning Patterns: {summary['reasoning_patterns_count']}")

    print(f"\n  Advice Patterns: {summary['advice_patterns_count']}")
    if summary['advice_categories']:
        print(f"  Categories: {', '.join(summary['advice_categories'])}")

    print()

    # テストクエリ
    print("🧪 Testing Knowledge Retrieval:")
    print()

    test_question = "What is Cross structure?"
    print(f"Q: {test_question}")
    answer = learner.find_similar_qa(test_question)
    if answer:
        print(f"A: {answer[:200]}...")
    else:
        print("A: No matching Q&A found")

    print()


if __name__ == "__main__":
    test_knowledge_learner()
