#!/usr/bin/env python3
"""
会話コンテキスト分離システム

異なるトピックの会話が混ざらないように、文脈を分離して学習
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime
import re


class ConversationContext:
    """会話の文脈を管理"""

    def __init__(self):
        self.contexts: List[Dict[str, Any]] = []
        self.current_context_id = None

    def create_new_context(self, user_input: str) -> str:
        """
        新しい会話コンテキストを作成

        Args:
            user_input: ユーザーの入力

        Returns:
            コンテキストID
        """
        context_id = f"ctx_{len(self.contexts)}_{int(datetime.now().timestamp())}"

        # トピック抽出
        topic = self._extract_topic(user_input)

        context = {
            'id': context_id,
            'topic': topic,
            'keywords': self._extract_keywords(user_input),
            'started_at': datetime.now().isoformat(),
            'messages': [],
            'active': True
        }

        self.contexts.append(context)
        self.current_context_id = context_id

        return context_id

    def should_create_new_context(self, user_input: str, previous_input: str = None) -> bool:
        """
        新しいコンテキストを作成すべきか判定

        Args:
            user_input: 現在のユーザー入力
            previous_input: 前回のユーザー入力

        Returns:
            新しいコンテキストを作成すべきか
        """
        # 最初の入力
        if not previous_input or not self.contexts:
            return True

        # トピックの変化を検出
        current_topic = self._extract_topic(user_input)
        previous_topic = self._extract_topic(previous_input)

        # 全く異なるトピック
        if not self._topics_related(current_topic, previous_topic):
            return True

        # 新しい質問パターン（「〜とは」など）が始まった
        if self._is_new_definition_question(user_input) and self._is_new_definition_question(previous_input):
            # 連続する定義質問だが、トピックが違う
            current_keywords = set(self._extract_keywords(user_input))
            previous_keywords = set(self._extract_keywords(previous_input))

            # キーワードの重複が少ない（20%未満）
            overlap = len(current_keywords & previous_keywords)
            total = len(current_keywords | previous_keywords)

            if total > 0 and overlap / total < 0.2:
                return True

        return False

    def add_message_to_context(self, role: str, content: str, context_id: str = None):
        """コンテキストにメッセージを追加"""
        if context_id is None:
            context_id = self.current_context_id

        if context_id is None:
            # コンテキストが存在しない場合、新規作成
            if role == 'user':
                context_id = self.create_new_context(content)
            else:
                return

        # コンテキストを検索
        for context in self.contexts:
            if context['id'] == context_id:
                context['messages'].append({
                    'role': role,
                    'content': content,
                    'timestamp': datetime.now().isoformat()
                })
                break

    def get_context_metadata(self, user_input: str) -> Dict[str, Any]:
        """
        メッセージのコンテキストメタデータを取得

        このメタデータをCross構造に保存することで、後で分離可能
        """
        if not self.current_context_id:
            return {}

        current_context = None
        for ctx in self.contexts:
            if ctx['id'] == self.current_context_id:
                current_context = ctx
                break

        if not current_context:
            return {}

        return {
            'context_id': self.current_context_id,
            'topic': current_context['topic'],
            'keywords': current_context['keywords'],
            'message_count': len(current_context['messages'])
        }

    def _extract_topic(self, text: str) -> str:
        """トピックを抽出"""
        # 「〜とは」パターン
        match = re.search(r'(.+?)とは', text)
        if match:
            return match.group(1).strip()

        # 「〜について」パターン
        match = re.search(r'(.+?)について', text)
        if match:
            return match.group(1).strip()

        # "What is X" パターン
        match = re.search(r'what is (.+?)[\?.]?$', text.lower())
        if match:
            return match.group(1).strip()

        # 最初の数単語をトピックとする
        words = text.split()[:3]
        return ' '.join(words)

    def _extract_keywords(self, text: str) -> List[str]:
        """キーワードを抽出"""
        # 記号を除去
        cleaned = re.sub(r'[^\w\s]', ' ', text)

        # 単語に分割
        words = cleaned.split()

        # ストップワードを除外
        stop_words = {
            'とは', 'について', 'は', 'が', 'を', 'に', 'で', 'と', 'の',
            'what', 'is', 'are', 'the', 'a', 'an', 'how', 'why'
        }

        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 1]

        return keywords[:5]  # 最大5個

    def _topics_related(self, topic1: str, topic2: str, threshold: float = 0.3) -> bool:
        """2つのトピックが関連しているか判定"""
        # 単語レベルでの類似度
        words1 = set(topic1.lower().split())
        words2 = set(topic2.lower().split())

        if not words1 or not words2:
            return False

        intersection = words1 & words2
        union = words1 | words2

        similarity = len(intersection) / len(union) if union else 0

        return similarity >= threshold

    def _is_new_definition_question(self, text: str) -> bool:
        """定義質問かどうか"""
        patterns = ['とは', 'って何', 'what is', 'what are']
        return any(p in text.lower() for p in patterns)


def enhance_message_with_context(
    user_input: str,
    context_separator: ConversationContext,
    previous_input: str = None
) -> Tuple[str, Dict[str, Any]]:
    """
    メッセージにコンテキスト情報を付与

    Args:
        user_input: ユーザー入力
        context_separator: コンテキスト分離器
        previous_input: 前回の入力

    Returns:
        (enhanced_message, context_metadata)
    """
    # 新しいコンテキストが必要か判定
    if context_separator.should_create_new_context(user_input, previous_input):
        context_id = context_separator.create_new_context(user_input)
        context_metadata = {
            'context_id': context_id,
            'is_new_context': True,
            'topic': context_separator._extract_topic(user_input)
        }
    else:
        context_metadata = context_separator.get_context_metadata(user_input)
        context_metadata['is_new_context'] = False

    # メッセージをコンテキストに追加
    context_separator.add_message_to_context('user', user_input)

    # コンテキスト情報を透明に付与（Claudeには見えるが、ユーザーには見えない）
    if context_metadata.get('is_new_context'):
        enhanced_message = f"""[Context: New topic - {context_metadata.get('topic', 'Unknown')}]

{user_input}"""
    else:
        enhanced_message = user_input

    return enhanced_message, context_metadata
