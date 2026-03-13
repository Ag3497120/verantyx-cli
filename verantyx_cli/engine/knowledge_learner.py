#!/usr/bin/env python3
"""
Knowledge Learner - Claude Codeの一般知識応答を学習

エージェント操作だけでなく、説明・概念・推論なども学習：
- 質問への回答パターン
- 概念説明
- 技術知識
- 推論プロセス
- アドバイス・提案

Spatial Search Integration:
- 6次元空間距離に基づく検索
- 品質ベースのマッチング
- エンティティ・意図ベースの関連度計算
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict

# Import spatial positioning components
from .jcross_interpreter import SpatialDataManager, SpatialPositionCalculator

# Import .jcross function executor
from .jcross_function_executor import JCrossFunctionExecutor

# Import autonomous learner
from .autonomous_learner import AutonomousLearner


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

        # 6次元空間配置マネージャー
        self.spatial_manager = SpatialDataManager()

        # .jcross FUNCTION実行エンジン
        patterns_file = Path(__file__).parent.parent / "templates" / "japanese_sentence_patterns.jcross"
        self.function_executor = JCrossFunctionExecutor(patterns_file)

        # 自律学習エンジン
        learning_queue_file = Path(".verantyx/learning_queue.json")
        autonomous_knowledge_file = Path(".verantyx/autonomous_knowledge.json")
        self.autonomous_learner = AutonomousLearner(learning_queue_file, autonomous_knowledge_file)

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

        # 起動時に自律学習を実行（バックグラウンド）
        self._run_autonomous_learning_on_startup()

    def _load_cross_memory(self) -> Dict:
        """Cross構造を読み込む"""
        if not self.cross_file.exists():
            return {'axes': {}}

        try:
            # .jcrossファイルを読み込む
            if str(self.cross_file).endswith('.jcross'):
                from .jcross_storage_processors import JCrossStorageEngine
                storage = JCrossStorageEngine(self.cross_file)
                # memory構造をaxes形式に変換
                return {'axes': storage.memory}
            else:
                # 従来の.json形式
                with open(self.cross_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to load Cross memory for knowledge learning: {e}")
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
        # FRONT軸のcurrent_conversationから直接学習（こちらが正確なデータ）
        current_conversation = front_axis.get('current_conversation', [])

        # ユーザー・アシスタントのペアを抽出
        for i in range(len(current_conversation) - 1):
            current_msg = current_conversation[i]
            next_msg = current_conversation[i + 1]

            # ユーザーの質問 → Claudeの応答のペアを探す
            if not isinstance(current_msg, dict) or not isinstance(next_msg, dict):
                continue

            if current_msg.get('role') != 'user' or next_msg.get('role') != 'assistant':
                continue

            user_input = current_msg.get('content', '')
            claude_response = next_msg.get('content', '')

            if not user_input or not claude_response:
                continue

            # コンテキストマーカーを抽出・除去
            cleaned_input, context_info = self._extract_context_marker(user_input)

            # Claude応答をクリーニング（ANSI制御文字と装飾を除去）
            cleaned_response = self._clean_claude_response(claude_response)

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
                    'response': cleaned_response[:1000],  # クリーニング済みの応答を使用
                    'keywords': keywords,
                    'learned_at': datetime.now().isoformat()
                }

                # コンテキスト情報を保存
                if context_info:
                    qa_entry['context'] = context_info

                self.learned_knowledge['qa_patterns'][pattern_key].append(qa_entry)

    def _clean_claude_response(self, response: str) -> str:
        """
        Claude応答から不要な装飾・制御文字を除去

        除去対象:
        - ANSI制御文字 (\r\n, \u001b, etc.)
        - ターミナル装飾 (─, ⏺, ✻, etc.)
        - スピナー表示 (Creating..., Swirling..., etc.)
        - UIプロンプト (>, ?, etc.)
        """
        import re

        # ANSIエスケープシーケンスを除去
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', response)

        # 制御文字を除去
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '')
        cleaned = cleaned.replace('\x00', '').replace('\x07', '')

        # ターミナル装飾文字を除去
        decorations = ['─', '✳', '✻', '✽', '✶', '✢', '⏺', '·', '⎿', '╭', '╰', '│', '├', '└', '┌', '┐', '┘', '━', '┃']
        for char in decorations:
            cleaned = cleaned.replace(char, '')

        # スピナー・進行状況表示を除去
        spinner_patterns = [
            r'(Creating|Swirling|Baking|Actualizing|Effecting|Coalescing|Wrangling|Herding|Billowing|Wandering|Moseying|Enchanting|Churning|Thinking|Mashing)…?\s*(?:\(esc to interrupt\))?',
            r'>\s*\n',  # 空のプロンプト
            r'\?\s+for shortcuts.*?\n',
            r'Tip:.*?(?:\n|$)',
            r'Thinking\s+(on|off)\s*\(tab to toggle\)',
            r'0;[^\n]*?\x07',  # ターミナルタイトル設定
            r'>\s*[^\n]{0,30}\n(?=>|\?|Creating|Swirling)',  # 短いプロンプト行
        ]
        for pattern in spinner_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

        # 連続する空白・改行を整理
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r' {2,}', ' ', cleaned)

        # 実際の回答部分のみを抽出（日本語または英語の文章が始まるまで）
        # 最初の意味のある文章を探す
        lines = cleaned.split('\n')
        meaningful_lines = []
        found_content = False

        for line in lines:
            line = line.strip()

            # UIノイズをスキップ
            if re.match(r'^[\s>?\-━─│┃⏺·]*$', line):
                continue
            if re.match(r'^>\s*.*とは\s*$', line):  # プロンプトエコー (> りんごとは)
                continue
            if re.match(r'^>\s*$', line):
                continue
            if re.match(r'^0;.*', line):  # ターミナルタイトル (0; りんご)
                continue
            if 'for shortcuts' in line.lower():
                continue

            if not line:
                if found_content:
                    meaningful_lines.append('')  # 空行を保持
                continue

            # 実際のコンテンツ（長い行、または日本語・英語の文章）
            # 日本語・漢字・ひらがな・カタカナを含む行は確実にコンテンツ
            has_japanese = any('\u3000' <= c <= '\u9fff' or '\uff00' <= c <= '\uffef' for c in line)
            is_long_content = len(line) > 30

            if has_japanese or is_long_content:
                found_content = True
                meaningful_lines.append(line)
            elif found_content and len(line) > 5:
                # 既にコンテンツが始まっていて、ある程度の長さがあれば追加
                meaningful_lines.append(line)

        cleaned = '\n'.join(meaningful_lines).strip()

        return cleaned

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

    def _normalize_question(self, question: str) -> Dict[str, str]:
        """
        質問を正規化形式に変換（セマンティック検索用）

        「openaiとは」「openai」「openaiって何」 -> 全て entity="openai" に統一

        Returns:
            {
                "entity": 抽出された実体,
                "intent": 質問の意図,
                "normalized": 正規化された質問,
                "original": 元の質問
            }
        """
        import re

        # パターン定義（semantic_operations.jcrossから移植）
        patterns = [
            (r'(.+?)とは', 'definition'),
            (r'(.+?)って何', 'definition'),
            (r'(.+?)について', 'explanation'),
            (r'(.+?)とは何ですか', 'definition'),
            (r'(.+?)の意味', 'definition'),
            (r'^([a-zA-Z0-9_]+)$', 'definition'),  # 単語のみ
        ]

        for pattern, intent in patterns:
            match = re.match(pattern, question.strip())
            if match:
                entity = match.group(1).strip()
                return {
                    "entity": entity,
                    "intent": intent,
                    "normalized": f"{entity}の定義を教えて",
                    "original": question
                }

        # パターンマッチしない場合
        return {
            "entity": question,
            "intent": "unknown",
            "normalized": question,
            "original": question
        }

    def find_similar_qa(self, user_question: str) -> Optional[str]:
        """
        類似Q&Aを検索（セマンティック検索対応 + 6次元空間検索）

        検索戦略:
        1. 従来のキーワードベース検索（learned_knowledge内）
        2. 6次元空間距離ベース検索（cross_memory内）

        Args:
            user_question: ユーザーの質問

        Returns:
            類似する過去の応答、見つからなければNone
        """
        # 1. 質問を正規化（実体抽出）
        normalized_data = self._normalize_question(user_question)
        entity = normalized_data["entity"].lower()
        intent = normalized_data["intent"]

        # 2. 実体ベースで検索（従来の方法 - learned_knowledge内）
        best_match = None
        best_score = 0

        for pattern_key, qa_list in self.learned_knowledge['qa_patterns'].items():
            for qa in qa_list:
                score = 0

                # 応答が空の場合はスキップ
                if not qa.get('response') or len(qa['response'].strip()) == 0:
                    continue

                # キーワードに実体が含まれているか（完全一致）
                keywords_lower = [k.lower() for k in qa['keywords']]
                if entity in keywords_lower:
                    score = 1.0
                # 質問文に実体が含まれているか（部分一致）
                elif entity in qa['question'].lower():
                    score = 0.9
                # 実体の各単語がキーワードに含まれているか（複合語対応）
                elif all(word in ' '.join(keywords_lower) for word in entity.split()):
                    score = 0.85
                # キーワードの類似度チェック（フォールバック）
                else:
                    stored_keywords = set(keywords_lower)
                    # 実体を単語に分割してキーワードに追加
                    entity_words = entity.split()
                    query_keywords = set(entity_words + self._extract_keywords(user_question))
                    query_keywords = {k.lower() for k in query_keywords}

                    if query_keywords:
                        intersection = stored_keywords & query_keywords
                        union = stored_keywords | query_keywords
                        score = len(intersection) / len(union) if len(union) > 0 else 0

                if score > best_score:
                    best_score = score
                    best_match = qa['response']

        # 類似度が30%以上なら採用
        if best_score >= 0.3:
            return best_match

        # 3. キーワード検索で見つからなかった場合、6次元空間検索を試行
        spatial_result = self._search_by_spatial_distance(entity, intent)
        if spatial_result:
            return spatial_result

        return None

    def _search_by_spatial_distance(
        self,
        entity: str,
        intent: str,
        max_distance: float = 2.0
    ) -> Optional[str]:
        """
        6次元空間距離に基づいてcross_memory内を検索

        Args:
            entity: 検索実体
            intent: 検索意図
            max_distance: 許容最大距離

        Returns:
            最も近い会話の応答、見つからない場合はNone
        """
        try:
            # cross_memoryから全会話を集める
            all_conversations = []

            if "FRONT" in self.cross_memory:
                if "current_conversation" in self.cross_memory["FRONT"]:
                    front_convs = self.cross_memory["FRONT"]["current_conversation"]
                    if isinstance(front_convs, list):
                        # role形式の会話をrole_pair形式に変換
                        for item in front_convs:
                            if isinstance(item, dict):
                                # すでにrole_pairを持っている場合
                                if "role_pair" in item:
                                    all_conversations.append(item)
                                # roleとcontentを持っている場合（単一メッセージ）
                                elif "role" in item and "content" in item:
                                    # 連続するuser/assistantペアを探す必要がある
                                    # 簡易実装: 個別メッセージとして扱う
                                    all_conversations.append(item)

            # 空間的検索を実行
            result = self.spatial_manager.search_by_spatial_distance(
                user_question=f"{entity}とは",
                entity=entity,
                intent=intent,
                conversations=all_conversations,
                max_distance=max_distance
            )

            if result and result.get("conversation"):
                conv = result["conversation"]

                # role_pair形式から応答を抽出
                if "role_pair" in conv:
                    for msg in conv["role_pair"]:
                        if msg.get("role") == "assistant":
                            response = msg.get("content", "")
                            # UIノイズをクリーン
                            cleaned = self._clean_ui_noise(response)
                            if len(cleaned.strip()) > 10:
                                return cleaned
                # 単一メッセージ形式
                elif "role" in conv and conv.get("role") == "assistant":
                    response = conv.get("content", "")
                    cleaned = self._clean_ui_noise(response)
                    if len(cleaned.strip()) > 10:
                        return cleaned

            return None

        except Exception as e:
            # エラーが発生してもフォールバック
            print(f"⚠️  Spatial search failed: {e}")
            return None

    def _clean_ui_noise(self, text: str) -> str:
        """UIノイズを除去"""
        # スピナー文字を除去
        spinner_chars = "⣾⣽⣻⢿⡿⣟⣯⣷"
        for char in spinner_chars:
            text = text.replace(char, "")

        # "> " プロンプトを除去
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

        # ボックス描画文字を除去
        box_chars = "│─┤┬┴├┼"
        for char in box_chars:
            text = text.replace(char, "")

        # 動詞パターン（Creating, Swirling, etc.）を除去
        noise_patterns = [
            r'\bCreating\b', r'\bSwirling\b', r'\bBaking\b', r'\bIncubating\b',
            r'\bSautéing\b', r'\bBrewing\b', r'\bCrafting\b', r'\bMixing\b',
            r'\bPreparing\b', r'\bCooking\b', r'\bDistilling\b', r'\bFermenting\b',
            r'\bGenerating\b', r'\bProcessing\b'
        ]
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text)

        # エスケープシーケンスを除去
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)

        # 複数の空白を1つに
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

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

    def generate_semantic_operations(self, question: str) -> List[str]:
        """
        質問から操作コマンドを自動生成（semantic_operations.jcrossの実装）

        Returns:
            操作コマンドのリスト
        """
        # 1. 質問を正規化
        normalized_data = self._normalize_question(question)

        operations = []

        # 2. 実体抽出コマンド
        operations.append(
            f"実体抽出 実体={normalized_data['entity']} 元の質問={normalized_data['original']}"
        )

        # 3. 意図分類コマンド
        operations.append(
            f"意図分類 意図={normalized_data['intent']} 実体={normalized_data['entity']}"
        )

        # 4. セマンティック検索コマンド
        operations.append(
            f"セマンティック検索 クエリ={normalized_data['normalized']} "
            f"実体={normalized_data['entity']} 意図={normalized_data['intent']}"
        )

        # 5. 応答選択コマンド
        operations.append(
            f"応答選択 実体={normalized_data['entity']} スコア閾値=0.3"
        )

        return operations

    def execute_semantic_search_with_operations(self, question: str) -> Dict[str, Any]:
        """
        セマンティック検索を操作コマンド付きで実行（.jcross FUNCTION使用）

        Returns:
            {
                "response": 応答テキスト,
                "operations": 実行された操作コマンドのリスト,
                "entity": 抽出された実体,
                "intent": 意図,
                "score": マッチスコア,
                "resolved_question": 代名詞解決後の質問
            }
        """
        # .jcross FUNCTIONで操作コマンド生成（代名詞解決、パターンマッチング、意味推測を含む）
        jcross_operations = self.function_executor.generate_operation_commands(
            question,
            self.function_executor.get_focus_stack()
        )

        # セマンティック検索実行
        response = self.find_similar_qa(question)

        # 応答が見つからなかった場合、自動改善ループ + 自律学習トリガー
        if not response:
            claude_query = self.function_executor.auto_improvement_loop(question)
            # 操作コマンドを保存（失敗）
            self.function_executor.save_operation_commands(jcross_operations, success=False)

            # 自律学習をトリガー（Wikipediaから自動取得）
            normalized_data = self._normalize_question(question)
            self.trigger_autonomous_learning_for_failure(
                question,
                normalized_data["entity"],
                {"confidence": 0.0}
            )
        else:
            # 操作コマンドを保存（成功）
            self.function_executor.save_operation_commands(jcross_operations, success=True)

        # 正規化データ取得
        normalized_data = self._normalize_question(question)

        # 代名詞解決後の質問を取得
        resolved_question = self.function_executor.simulate_cross_resolution(question)

        return {
            "response": response,
            "operations": jcross_operations,  # .jcross FUNCTIONで生成された操作コマンド
            "entity": normalized_data["entity"],
            "intent": normalized_data["intent"],
            "score": 1.0 if response else 0.0,
            "resolved_question": resolved_question
        }

    def _run_autonomous_learning_on_startup(self):
        """
        起動時に自律学習を実行（高優先度タスクのみ）
        """
        try:
            # 高優先度タスク（優先度>=7）を最大3件処理
            stats = self.autonomous_learner.execute_autonomous_learning(max_tasks=3)

            if stats["knowledge_acquired"] > 0:
                print(f"✅ 自律学習完了: {stats['knowledge_acquired']}件の知識を獲得")

                # 学習した知識を適用
                apply_stats = self.autonomous_learner.apply_learned_knowledge()
                if apply_stats["qa_patterns_added"] > 0:
                    print(f"📚 新しいQ&Aパターンを{apply_stats['qa_patterns_added']}件追加")

                    # 学習した知識をKnowledgeLearnerに統合
                    self._integrate_autonomous_knowledge()

        except Exception as e:
            # エラーが発生しても起動を妨げない
            print(f"⚠️  自律学習でエラーが発生しましたが、続行します: {e}")

    def _integrate_autonomous_knowledge(self):
        """
        自律学習で獲得した知識をKnowledgeLearnerに統合
        """
        try:
            knowledge_file = Path(".verantyx/autonomous_knowledge.json")
            if not knowledge_file.exists():
                return

            with open(knowledge_file, 'r', encoding='utf-8') as f:
                autonomous_knowledge = json.load(f)

            auto_learned = autonomous_knowledge.get("auto_learned_patterns", [])

            for qa in auto_learned:
                if qa.get("applied") and qa.get("confidence", 0) > 0.7:
                    # Q&Aパターンとして追加
                    pattern_key = qa.get("entity", "general")

                    if pattern_key not in self.learned_knowledge['qa_patterns']:
                        self.learned_knowledge['qa_patterns'][pattern_key] = []

                    # 既に存在しないかチェック
                    exists = any(
                        p.get("question") == qa["question"]
                        for p in self.learned_knowledge['qa_patterns'][pattern_key]
                    )

                    if not exists:
                        self.learned_knowledge['qa_patterns'][pattern_key].append({
                            "question": qa["question"],
                            "response": qa["response"],
                            "keywords": qa.get("keywords", []),
                            "source": qa.get("source", "autonomous"),
                            "auto_learned": True
                        })

        except Exception as e:
            print(f"⚠️  自律学習知識の統合に失敗: {e}")

    def trigger_autonomous_learning_for_failure(
        self,
        failed_question: str,
        entity: str,
        context: Dict[str, Any]
    ):
        """
        失敗した質問に対して自律学習をトリガー

        Args:
            failed_question: 失敗した質問
            entity: 抽出された実体
            context: 失敗時のコンテキスト
        """
        # 失敗を分析
        analysis = self.autonomous_learner.analyze_failure(
            failed_question,
            "no_response_found",
            {
                "entity": entity,
                "confidence": context.get("confidence", 0.0),
                "timestamp": datetime.now().isoformat()
            }
        )

        # 学習キューに追加
        learning_queue_file = Path(".verantyx/learning_queue.json")
        learning_queue_file.parent.mkdir(parents=True, exist_ok=True)

        if learning_queue_file.exists():
            with open(learning_queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        else:
            queue = []

        # 重複チェック
        exists = any(task.get("question") == failed_question for task in queue)
        if not exists:
            queue.append({
                "question": failed_question,
                "entity": entity,
                "priority": analysis["priority"],
                "status": "pending",
                "added_at": datetime.now().isoformat()
            })

            with open(learning_queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, ensure_ascii=False, indent=2)

            print(f"📝 学習キューに追加: {failed_question} (優先度: {analysis['priority']})")


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
