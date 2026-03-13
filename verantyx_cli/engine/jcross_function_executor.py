#!/usr/bin/env python3
"""
JCross Function Executor
.jcrossファイルのFUNCTION定義を実行
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class JCrossFunctionExecutor:
    """
    .jcrossファイルに定義されたFUNCTIONを実行するエンジン
    """

    def __init__(self, patterns_file: Path):
        self.patterns_file = patterns_file
        self.patterns = self._load_patterns()
        self.focus_stack = []  # 焦点スタック
        self.operation_history = []  # 操作コマンド履歴

    def _load_patterns(self) -> Dict[str, Any]:
        """パターンを読み込み"""
        return {
            "definition": [
                r"(.+?)とは",
                r"(.+?)って何",
                r"(.+?)の意味",
                r"(.+?)について",
                r"^([a-zA-Z0-9_\s]+)$"
            ],
            "explanation": [
                r"(.+?)について教えて",
                r"(.+?)を説明して",
                r"(.+?)はどういうもの"
            ],
            "how_to": [
                r"(.+?)のやり方",
                r"(.+?)はどうやる",
                r"どうやって(.+?)する"
            ],
            "pronoun": [
                r"それ(とは|って何|について|は|を|の)",
                r"これ(とは|って何|について|は|を|の)",
                r"あれ(とは|って何|について|は|を|の)"
            ]
        }

    def match_japanese_pattern(self, text: str) -> Optional[Dict[str, Any]]:
        """日本語パターンマッチング"""
        for intent, pattern_list in self.patterns.items():
            for pattern in pattern_list:
                match = re.match(pattern, text.strip())
                if match:
                    entity = match.group(1) if match.groups() else text
                    return {
                        "pattern": pattern,
                        "matched_text": text,
                        "entity": entity.strip(),
                        "intent": intent,
                        "normalized": f"{entity.strip()}の定義を教えて"
                    }
        return None

    def simulate_cross_resolution(self, text: str, focus_stack: Optional[List[str]] = None) -> str:
        """代名詞解決"""
        if focus_stack is None:
            focus_stack = self.focus_stack

        resolved_text = text
        pronoun_mappings = {
            "それ": -1,
            "その": -1,
            "これ": -1,
            "この": -1,
            "あれ": -2,
            "あの": -2
        }

        for pronoun, stack_index in pronoun_mappings.items():
            if pronoun in resolved_text and len(focus_stack) >= abs(stack_index):
                entity = focus_stack[stack_index]
                resolved_text = resolved_text.replace(pronoun, entity)

        return resolved_text

    def infer_meaning_from_examples(self, unknown_sentence: str) -> Optional[Dict[str, Any]]:
        """例文から意味を推測"""
        entity_match = re.match(r'(.+?)(は|が|を|の|とは|って)', unknown_sentence)
        if entity_match:
            return {
                "original": unknown_sentence,
                "inferred_intent": "definition",
                "inferred_entity": entity_match.group(1).strip(),
                "confidence": 0.7
            }
        return None

    def generate_operation_commands(self, question: str, focus_stack: Optional[List[str]] = None) -> List[str]:
        """操作コマンド自動生成"""
        if focus_stack is None:
            focus_stack = self.focus_stack

        commands = []

        # Step 1: 代名詞解決
        resolved_question = self.simulate_cross_resolution(question, focus_stack)
        if resolved_question != question:
            commands.append(f"代名詞解決 元={question} 解決後={resolved_question}")

        # Step 2: パターンマッチング
        matched = self.match_japanese_pattern(resolved_question)

        if matched:
            commands.append(f"実体抽出 実体={matched['entity']} 意図={matched['intent']}")
            commands.append(f"パターンマッチング パターン={matched['pattern']}")
            commands.append(f"正規化 正規化形式={matched['normalized']}")
            commands.append(f"セマンティック検索 クエリ={matched['normalized']} 実体={matched['entity']} 意図={matched['intent']}")
            commands.append(f"応答選択 実体={matched['entity']} スコア閾値=0.3")

            if matched['entity'] not in focus_stack:
                focus_stack.append(matched['entity'])

        else:
            inferred = self.infer_meaning_from_examples(resolved_question)

            if inferred:
                commands.append(f"意味推測 元={resolved_question} 推測意図={inferred['inferred_intent']} 信頼度={inferred['confidence']:.2f}")
                commands.append(f"実体抽出(推測) 実体={inferred['inferred_entity']}")
                commands.append(f"セマンティック検索 クエリ={inferred['inferred_entity']} 意図={inferred['inferred_intent']}")

                if inferred['inferred_entity'] not in focus_stack:
                    focus_stack.append(inferred['inferred_entity'])
            else:
                commands.append(f"学習対象マーク 質問={resolved_question} 理由=パターン不一致")

        self.operation_history.append({
            "question": question,
            "commands": commands,
            "timestamp": datetime.now().isoformat()
        })

        return commands

    def auto_improvement_loop(self, failed_question: str) -> str:
        """自動改善ループ"""
        self._mark_for_learning(failed_question)

        claude_query = f"""{failed_question}

この質問について、詳しく教えてください。
スタンドアロンモードで次回から答えられるよう、学習します。
"""
        return claude_query

    def _mark_for_learning(self, question: str):
        """学習対象マーク"""
        learning_file = Path(".verantyx/learning_queue.json")
        learning_file.parent.mkdir(parents=True, exist_ok=True)

        if learning_file.exists():
            with open(learning_file, 'r', encoding='utf-8') as f:
                learning_queue = json.load(f)
        else:
            learning_queue = []

        learning_queue.append({
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        })

        with open(learning_file, 'w', encoding='utf-8') as f:
            json.dump(learning_queue, f, ensure_ascii=False, indent=2)

    def save_operation_commands(self, commands: List[str], success: bool):
        """操作コマンドを保存"""
        commands_file = Path(".verantyx/operation_commands.json")
        commands_file.parent.mkdir(parents=True, exist_ok=True)

        if commands_file.exists():
            with open(commands_file, 'r', encoding='utf-8') as f:
                all_commands = json.load(f)
        else:
            all_commands = {
                "recent_commands": [],
                "successful_commands": [],
                "failed_commands": []
            }

        command_record = {
            "commands": commands,
            "timestamp": datetime.now().isoformat(),
            "success": success
        }

        all_commands["recent_commands"].append(command_record)

        if success:
            all_commands["successful_commands"].append(command_record)
        else:
            all_commands["failed_commands"].append(command_record)

        with open(commands_file, 'w', encoding='utf-8') as f:
            json.dump(all_commands, f, ensure_ascii=False, indent=2)

    def get_focus_stack(self) -> List[str]:
        """焦点スタック取得"""
        return self.focus_stack.copy()

    def update_focus_stack(self, entity: str):
        """焦点スタック更新"""
        if entity not in self.focus_stack:
            self.focus_stack.append(entity)
        if len(self.focus_stack) > 10:
            self.focus_stack = self.focus_stack[-10:]
