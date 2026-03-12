#!/usr/bin/env python3
"""
文脈解決エンジン - 代名詞解決・QA追跡・会話履歴管理

機能:
1. 代名詞解決（それ、これ、その、あの など）
2. QA対応関係の記録
3. 会話履歴の追跡
4. 焦点実体の管理
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import deque


class ContextResolver:
    """
    文脈解決エンジン

    原則:
    - 代名詞は直前の焦点実体を参照
    - QA対応はペアとして記録
    - 会話履歴は双方向リンク
    - 焦点実体は会話ごとに更新
    """

    def __init__(self, storage_file: Optional[str] = None):
        """
        Args:
            storage_file: 永続化ファイルのパス（.jcross形式）
        """
        # 永続化ファイル
        self.storage_file = storage_file

        # QA履歴（質問と応答のペア）
        self.qa_history = []  # [{question, answer, entities, focus, context_id}]

        # 焦点実体スタック（直近の重要実体）
        self.focus_stack = deque(maxlen=5)  # 最大5つまで記憶

        # コンテキスト間の依存関係
        self.context_dependencies = {}  # {context_id: {depends_on, pronouns}}

        # 代名詞パターン
        self.pronouns = {
            'ja': ['それ', 'これ', 'あれ', 'その', 'この', 'あの',
                   'そこ', 'ここ', 'あそこ', '同じ', '前の', '先の'],
            'en': ['it', 'this', 'that', 'these', 'those', 'the same', 'previous']
        }

        # セッション間で永続化するデータを復元
        if storage_file:
            self._load_from_storage()

    def resolve_pronouns(self, text: str, context_id: str) -> Dict[str, Any]:
        """
        テキスト中の代名詞を解決

        Args:
            text: ユーザー入力テキスト
            context_id: 現在のコンテキストID

        Returns:
            解決結果: {
                'resolved': bool,
                'pronouns_found': [代名詞リスト],
                'resolutions': {代名詞: 解決先},
                'resolved_text': 解決済みテキスト
            }
        """
        pronouns_found = []
        resolutions = {}

        # 代名詞を検出
        for lang, pronoun_list in self.pronouns.items():
            for pronoun in pronoun_list:
                if pronoun in text:
                    pronouns_found.append(pronoun)

        if not pronouns_found:
            return {
                'resolved': False,
                'pronouns_found': [],
                'resolutions': {},
                'resolved_text': text
            }

        # 焦点実体から解決先を取得
        if not self.focus_stack:
            # 焦点実体がない場合は解決できない
            return {
                'resolved': False,
                'pronouns_found': pronouns_found,
                'resolutions': {},
                'resolved_text': text,
                'error': 'No focus entity available'
            }

        # 直前の焦点実体を取得
        focus_entity = self.focus_stack[-1]

        # 各代名詞を解決
        resolved_text = text
        for pronoun in pronouns_found:
            resolutions[pronoun] = focus_entity['entity']

            # テキスト中の代名詞を置換（カッコ付きで明示）
            resolved_text = resolved_text.replace(
                pronoun,
                f"{pronoun}[={focus_entity['entity']}]"
            )

        # 依存関係を記録
        if focus_entity.get('context_id'):
            self.context_dependencies[context_id] = {
                'depends_on': focus_entity['context_id'],
                'pronouns': resolutions,
                'focus_entity': focus_entity['entity']
            }

        return {
            'resolved': True,
            'pronouns_found': pronouns_found,
            'resolutions': resolutions,
            'resolved_text': resolved_text,
            'focus_entity': focus_entity
        }

    def add_qa_pair(
        self,
        question: str,
        answer: str,
        context_id: str,
        entities: List[str] = None,
        focus_entity: str = None
    ) -> Dict[str, Any]:
        """
        質問-応答ペアを記録

        Args:
            question: ユーザーの質問
            answer: Claudeの応答
            context_id: コンテキストID
            entities: 抽出された実体リスト
            focus_entity: 焦点実体

        Returns:
            QAペア情報
        """
        # 代名詞を解決
        pronoun_resolution = self.resolve_pronouns(question, context_id)

        # QAペアを作成
        qa_pair = {
            'id': f"qa_{len(self.qa_history)}",
            'question': question,
            'answer': answer,
            'context_id': context_id,
            'entities': entities or [],
            'focus_entity': focus_entity,
            'timestamp': datetime.now().isoformat(),
            'pronouns': pronoun_resolution.get('resolutions', {}),
            'depends_on': None,
            'previous_qa': None,
            'next_qa': None
        }

        # 前のQAとリンク
        if self.qa_history:
            prev_qa = self.qa_history[-1]
            qa_pair['previous_qa'] = prev_qa['id']
            prev_qa['next_qa'] = qa_pair['id']

            # 代名詞があれば依存関係を記録
            if pronoun_resolution['resolved']:
                qa_pair['depends_on'] = prev_qa['id']

        # 履歴に追加
        self.qa_history.append(qa_pair)

        # 焦点実体を更新
        if focus_entity:
            self._update_focus(focus_entity, context_id)

        return qa_pair

    def _update_focus(self, entity: str, context_id: str):
        """
        焦点実体を更新

        重要な実体（質問の主題）を記憶する
        """
        focus_info = {
            'entity': entity,
            'context_id': context_id,
            'timestamp': datetime.now().isoformat()
        }

        # 既に同じ実体があればスタックの先頭に移動
        self.focus_stack = deque(
            [f for f in self.focus_stack if f['entity'] != entity],
            maxlen=5
        )

        # 新しい焦点を追加
        self.focus_stack.append(focus_info)

    def get_conversation_chain(
        self,
        context_id: str,
        max_depth: int = 10
    ) -> List[Dict]:
        """
        会話の連鎖を取得（QA IDの依存関係を遡る）

        Args:
            context_id: 開始コンテキストID
            max_depth: 最大遡及深度

        Returns:
            会話チェーン（古い順）
        """
        # 指定されたコンテキストのQAを取得
        start_qa = self._find_qa_by_context(context_id)
        if not start_qa:
            return []

        chain = [start_qa]
        current_qa = start_qa
        depth = 0

        # previous_qaリンクを遡る
        while current_qa and depth < max_depth:
            prev_qa_id = current_qa.get('previous_qa')
            if not prev_qa_id:
                break

            # previous_qaを検索
            prev_qa = None
            for qa in self.qa_history:
                if qa['id'] == prev_qa_id:
                    prev_qa = qa
                    break

            if not prev_qa:
                break

            chain.insert(0, prev_qa)  # 先頭に挿入（古い順）
            current_qa = prev_qa
            depth += 1

        return chain

    def _find_qa_by_context(self, context_id: str) -> Optional[Dict]:
        """コンテキストIDからQAペアを検索"""
        for qa in reversed(self.qa_history):
            if qa['context_id'] == context_id:
                return qa
        return None

    def search_qa_by_entity(self, entity: str) -> List[Dict]:
        """
        焦点実体でQAペアを検索

        Args:
            entity: 検索する実体名（例: "りんご"）

        Returns:
            マッチしたQAペアのリスト
        """
        results = []
        for qa in self.qa_history:
            if qa.get('focus_entity') == entity:
                results.append(qa)
            elif entity in qa.get('entities', []):
                results.append(qa)
        return results

    def search_qa_by_keyword(self, keyword: str) -> List[Dict]:
        """
        キーワードでQAペアを検索

        Args:
            keyword: 検索キーワード

        Returns:
            マッチしたQAペアのリスト
        """
        results = []
        for qa in self.qa_history:
            if keyword in qa.get('question', '') or keyword in qa.get('answer', ''):
                results.append(qa)
        return results

    def get_recent_context(self, n: int = 5) -> List[Dict]:
        """
        最近のQAペアを取得

        Args:
            n: 取得する件数

        Returns:
            最近のQAペアのリスト
        """
        return list(self.qa_history[-n:]) if self.qa_history else []

    def get_context_summary(self) -> str:
        """
        現在のコンテキスト状態のサマリーを取得

        Returns:
            人間が読めるサマリー文字列
        """
        lines = []
        lines.append("=== Context Summary ===")
        lines.append(f"Total QA pairs: {len(self.qa_history)}")
        lines.append(f"Focus stack size: {len(self.focus_stack)}")

        if self.focus_stack:
            lines.append("\nCurrent focus entities:")
            for i, focus in enumerate(reversed(self.focus_stack), 1):
                lines.append(f"  {i}. {focus['entity']} (from {focus['context_id']})")

        if self.qa_history:
            lines.append("\nRecent conversations:")
            recent = self.get_recent_context(3)
            for qa in recent:
                q_preview = qa['question'][:50]
                lines.append(f"  Q: {q_preview}{'...' if len(qa['question']) > 50 else ''}")
                lines.append(f"     Focus: {qa.get('focus_entity', 'unknown')}")

                if qa.get('pronouns'):
                    lines.append(f"     Pronouns: {qa['pronouns']}")

        if self.context_dependencies:
            lines.append(f"\nContext dependencies: {len(self.context_dependencies)} chains")

        return '\n'.join(lines)

    def extract_focus_entity(
        self,
        question: str,
        answer: str
    ) -> Optional[str]:
        """
        質問と応答から焦点実体を抽出

        例:
        - "りんごとは？" → "りんご"
        - "それは何科？" → 代名詞なので前の焦点
        """
        # 「〜とは」パターン
        match = re.search(r'(.+?)とは', question)
        if match:
            entity = match.group(1).strip()
            # 代名詞でなければ焦点実体
            if entity not in self.pronouns['ja']:
                return entity

        # 「〜について」パターン
        match = re.search(r'(.+?)について', question)
        if match:
            entity = match.group(1).strip()
            if entity not in self.pronouns['ja']:
                return entity

        # 応答の最初の名詞を抽出（簡易版）
        # "りんごは、バラ科..." → "りんご"
        match = re.search(r'^(.+?)は[、,]', answer)
        if match:
            entity = match.group(1).strip()
            # 記号を除去
            entity = re.sub(r'[「」『』（）()]', '', entity)
            if entity and entity not in self.pronouns['ja']:
                return entity

        return None

    def generate_context_operations(
        self,
        question: str,
        answer: str,
        context_id: str
    ) -> List[str]:
        """
        文脈理解のための操作コマンドを生成

        Returns:
            JCross操作コマンドのリスト
        """
        operations = []

        # 焦点実体を抽出
        focus_entity = self.extract_focus_entity(question, answer)

        # 代名詞を解決
        pronoun_resolution = self.resolve_pronouns(question, context_id)

        # 操作1: 代名詞解決
        if pronoun_resolution['resolved']:
            for pronoun, resolved in pronoun_resolution['resolutions'].items():
                op = f"参照解決 代名詞={pronoun} 参照先={resolved} " \
                     f"コンテキスト={pronoun_resolution['focus_entity']['context_id']}"
                operations.append(op)

        # 操作2: QA対応記録
        qa_pair = self.add_qa_pair(
            question,
            answer,
            context_id,
            focus_entity=[focus_entity] if focus_entity else []
        )

        op = f"QA対応 質問ID={qa_pair['id']} " \
             f"質問内容={question[:20]}... " \
             f"応答ID=a_{qa_pair['id']} " \
             f"焦点実体={focus_entity or 'unknown'}"
        operations.append(op)

        # 操作3: 依存関係記録
        if qa_pair['depends_on']:
            op = f"依存関係 質問ID={qa_pair['id']} " \
                 f"依存先={qa_pair['depends_on']} " \
                 f"依存タイプ=追加質問"
            operations.append(op)

        # 操作4: 焦点更新
        if focus_entity:
            op = f"焦点更新 実体={focus_entity} コンテキスト={context_id}"
            operations.append(op)

        return operations

    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        total_pronouns = sum(
            1 for qa in self.qa_history if qa.get('pronouns')
        )

        total_dependencies = len(self.context_dependencies)

        return {
            'total_qa_pairs': len(self.qa_history),
            'total_pronouns_resolved': total_pronouns,
            'total_context_dependencies': total_dependencies,
            'focus_stack_size': len(self.focus_stack),
            'current_focus': self.focus_stack[-1]['entity'] if self.focus_stack else None
        }

    def export_to_jcross(self) -> str:
        """
        文脈情報を.jcross形式で出力

        Returns:
            JCross形式の文字列
        """
        lines = []

        lines.append('"""')
        lines.append('文脈解決エンジン - 会話履歴と依存関係')
        lines.append('')
        lines.append(f'生成日時: {datetime.now().isoformat()}')
        lines.append(f'総QA数: {len(self.qa_history)}')
        lines.append('"""')
        lines.append('')
        lines.append('CROSS context_resolution {')
        lines.append('')

        # QA履歴
        lines.append('    // QA対応履歴')
        lines.append('    AXIS QA_HISTORY {')
        lines.append('        qa_pairs: [')
        for qa in self.qa_history:
            lines.append('            {')
            lines.append(f'                id: "{qa["id"]}",')
            lines.append(f'                question: "{qa["question"][:50]}...",')
            lines.append(f'                answer: "{qa["answer"][:50]}...",')
            lines.append(f'                focus_entity: "{qa.get("focus_entity", "unknown")}",')
            lines.append(f'                pronouns: {qa.get("pronouns", {})},')
            lines.append(f'                depends_on: "{qa.get("depends_on", "none")}",')
            lines.append(f'                context_id: "{qa["context_id"]}"')
            lines.append('            },')
        lines.append('        ]')
        lines.append('    }')
        lines.append('')

        # 焦点スタック
        lines.append('    // 焦点実体スタック')
        lines.append('    AXIS FOCUS_STACK {')
        lines.append('        entities: [')
        for focus in self.focus_stack:
            lines.append(f'            {{entity: "{focus["entity"]}", '
                        f'context: "{focus["context_id"]}"}},')
        lines.append('        ]')
        lines.append('    }')
        lines.append('')

        # 依存関係
        lines.append('    // コンテキスト依存関係')
        lines.append('    AXIS DEPENDENCIES {')
        lines.append('        relationships: {')
        for ctx_id, dep in self.context_dependencies.items():
            lines.append(f'            "{ctx_id}": {{')
            lines.append(f'                depends_on: "{dep.get("depends_on")}",')
            lines.append(f'                pronouns: {dep.get("pronouns", {})},')
            lines.append(f'                focus: "{dep.get("focus_entity")}"')
            lines.append('            },')
        lines.append('        }')
        lines.append('    }')
        lines.append('')

        lines.append('}')

        return '\n'.join(lines)

    def _load_from_storage(self):
        """
        .jcrossファイルから永続化データを復元
        """
        from pathlib import Path
        import json

        if not self.storage_file:
            return

        storage_path = Path(self.storage_file)
        if not storage_path.exists():
            return

        try:
            with open(storage_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 簡易パース（JSONセクションを抽出）
            # 実際の.jcross形式では専用パーサーが必要だが、
            # ここでは互換性のためJSON形式も受け付ける
            if content.startswith('{'):
                data = json.loads(content)
            else:
                # .jcross形式からデータ抽出（簡易版）
                data = self._parse_jcross_format(content)

            # QA履歴を復元
            if 'qa_history' in data:
                self.qa_history = data['qa_history']

            # 焦点スタックを復元
            if 'focus_stack' in data:
                self.focus_stack = deque(data['focus_stack'], maxlen=5)

            # 依存関係を復元
            if 'context_dependencies' in data:
                self.context_dependencies = data['context_dependencies']

            print(f"✅ Context restored: {len(self.qa_history)} QA pairs, "
                  f"{len(self.focus_stack)} focus entities")

        except Exception as e:
            print(f"⚠️  Failed to restore context: {e}")

    def _parse_jcross_format(self, content: str) -> Dict:
        """
        .jcross形式の簡易パース（JSON互換部分を抽出）
        """
        # TODO: 完全な.jcrossパーサーを実装
        # 現在は空のデータを返す
        return {
            'qa_history': [],
            'focus_stack': [],
            'context_dependencies': {}
        }

    def save_to_storage(self):
        """
        現在の状態を.jcrossファイルに保存
        """
        from pathlib import Path
        import json

        if not self.storage_file:
            return

        storage_path = Path(self.storage_file)
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # シンプルなJSON形式で保存（.jcross形式との互換性を保つ）
            data = {
                'qa_history': self.qa_history,
                'focus_stack': list(self.focus_stack),
                'context_dependencies': self.context_dependencies,
                'saved_at': datetime.now().isoformat()
            }

            with open(storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"⚠️  Failed to save context: {e}")
