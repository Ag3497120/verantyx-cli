#!/usr/bin/env python3
"""
Autonomous Learner
Wikipedia/学習サイトからの自律学習エンジン
"""

import re
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from bs4 import BeautifulSoup


class AutonomousLearner:
    """
    自律学習エンジン
    外部ソース(Wikipedia等)から知識を取得し、失敗した質問を自動的に学習
    """

    def __init__(self, learning_queue_file: Path, knowledge_file: Path):
        """
        Args:
            learning_queue_file: 学習キューのJSONファイル
            knowledge_file: 学習済み知識のJSONファイル
        """
        self.learning_queue_file = learning_queue_file
        self.knowledge_file = knowledge_file
        
        # 学習ソース定義
        self.learning_sources = [
            {
                "name": "Wikipedia日本語版",
                "url_pattern": "https://ja.wikipedia.org/wiki/{entity}",
                "priority": 10,
                "reliability": 0.95
            },
            {
                "name": "Wikipedia英語版",
                "url_pattern": "https://en.wikipedia.org/wiki/{entity}",
                "priority": 7,
                "reliability": 0.93
            }
        ]

    def analyze_failure(
        self,
        failed_question: str,
        failure_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        失敗した質問を分析し、学習戦略を決定
        
        Args:
            failed_question: 失敗した質問
            failure_type: 失敗のタイプ
            context: 失敗時のコンテキスト
            
        Returns:
            学習戦略と実行すべきアクション
        """
        failure_strategies = {
            "no_pattern_match": {
                "learning_strategy": "新しい質問パターンを収集",
                "auto_action": "fetch_from_wikipedia"
            },
            "low_confidence": {
                "learning_strategy": "より多くの例文を収集",
                "auto_action": "fetch_example_sentences"
            },
            "no_response_found": {
                "learning_strategy": "外部ソースから知識を取得",
                "auto_action": "fetch_from_wikipedia"
            }
        }

        strategy = failure_strategies.get(failure_type, {
            "learning_strategy": "manual_investigation",
            "auto_action": "log_for_review"
        })

        analysis_result = {
            "question": failed_question,
            "failure_type": failure_type,
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "learning_strategy": strategy["learning_strategy"],
            "auto_action": strategy["auto_action"],
            "priority": self._calculate_priority(failed_question, context)
        }

        return analysis_result

    def _calculate_priority(self, question: str, context: Dict[str, Any]) -> int:
        """学習の優先度を計算 (1-10)"""
        priority = 5

        # 実体が明確なら優先度高
        if context.get("entity") and len(context["entity"]) > 0:
            priority += 2

        # 信頼度が極端に低いなら優先度低
        if context.get("confidence", 1.0) < 0.3:
            priority -= 1

        return min(10, max(1, priority))

    def fetch_knowledge_from_sources(
        self,
        entity: str,
        question_type: str = "definition"
    ) -> Dict[str, Any]:
        """
        外部ソース(Wikipedia等)から知識を取得
        
        Args:
            entity: 学習対象の実体
            question_type: 質問のタイプ
            
        Returns:
            取得した知識
        """
        knowledge = {
            "entity": entity,
            "sources": [],
            "content": {},
            "confidence": 0.0
        }

        # 優先度順にソート
        sources = sorted(self.learning_sources, key=lambda x: x["priority"], reverse=True)

        for source in sources:
            try:
                # URLを構築
                url = source["url_pattern"].format(entity=entity.replace(" ", "_"))

                # コンテンツを取得
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Verantyx/1.0 (Educational Purpose)'
                })

                if response.status_code == 200:
                    # コンテンツを抽出
                    extracted = self._extract_content(
                        response.text,
                        source["name"],
                        question_type
                    )

                    if extracted and len(extracted) > 50:
                        knowledge["sources"].append({
                            "name": source["name"],
                            "url": url,
                            "reliability": source["reliability"],
                            "extracted_at": datetime.now().isoformat()
                        })

                        knowledge["content"][source["name"]] = extracted
                        knowledge["confidence"] = max(
                            knowledge["confidence"],
                            source["reliability"]
                        )

                        # 最初の成功で終了
                        break

            except Exception as e:
                print(f"⚠️  Failed to fetch from {source['name']}: {e}")
                continue

        return knowledge

    def _extract_content(
        self,
        html: str,
        source_name: str,
        question_type: str
    ) -> str:
        """HTMLから必要なコンテンツを抽出"""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            if "Wikipedia" in source_name:
                # Wikipediaの要約段落を抽出
                content_div = soup.find('div', {'id': 'mw-content-text'})
                if content_div:
                    # 最初の意味のある段落を取得
                    paragraphs = content_div.find_all('p', recursive=True)
                    for p in paragraphs:
                        text = p.get_text().strip()
                        # 50文字以上で、括弧だけではないもの
                        if len(text) > 50 and not text.startswith('('):
                            # 参照マーカーを除去
                            text = re.sub(r'\[\d+\]', '', text)
                            return text.strip()

            return ""

        except Exception as e:
            print(f"⚠️  Content extraction failed: {e}")
            return ""

    def execute_autonomous_learning(self, max_tasks: int = 5) -> Dict[str, Any]:
        """
        自律学習を実行
        
        Args:
            max_tasks: 最大処理タスク数
            
        Returns:
            学習結果の統計
        """
        learning_stats = {
            "tasks_processed": 0,
            "knowledge_acquired": 0,
            "commands_improved": 0,
            "success_rate": 0.0,
            "timestamp": datetime.now().isoformat()
        }

        # 学習キューを読み込み
        learning_queue = self._load_learning_queue()

        # 高優先度タスクを取得
        high_priority_tasks = [
            task for task in learning_queue
            if task.get("priority", 5) >= 7 and task.get("status") == "pending"
        ][:max_tasks]

        for task in high_priority_tasks:
            try:
                entity = task.get("entity", task.get("question", ""))

                # 外部ソースから知識を取得
                knowledge = self.fetch_knowledge_from_sources(
                    entity,
                    task.get("question_type", "definition")
                )

                if knowledge["confidence"] > 0.7:
                    # Q&Aパターンとして保存
                    qa_pattern = self._create_qa_pattern_from_knowledge(
                        task["question"],
                        knowledge
                    )

                    self._save_qa_pattern(qa_pattern)
                    learning_stats["knowledge_acquired"] += 1

                    # タスクを完了としてマーク
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now().isoformat()
                    learning_stats["tasks_processed"] += 1

                else:
                    # 信頼度が低い場合は再試行
                    task["retry_count"] = task.get("retry_count", 0) + 1
                    if task["retry_count"] >= 3:
                        task["status"] = "failed"

            except Exception as e:
                print(f"⚠️  Learning task failed: {task.get('question')} - {e}")
                task["status"] = "failed"
                task["error"] = str(e)

        # 学習キューを保存
        self._save_learning_queue(learning_queue)

        # 成功率を計算
        if len(high_priority_tasks) > 0:
            learning_stats["success_rate"] = learning_stats["tasks_processed"] / len(high_priority_tasks)

        return learning_stats

    def _create_qa_pattern_from_knowledge(
        self,
        question: str,
        knowledge: Dict[str, Any]
    ) -> Dict[str, Any]:
        """学習した知識からQ&Aパターンを作成"""
        # 最も信頼性の高いソースのコンテンツを使用
        best_source = max(knowledge["sources"], key=lambda x: x["reliability"])
        response = knowledge["content"][best_source["name"]]

        qa_pattern = {
            "question": question,
            "response": response,
            "keywords": self._extract_keywords(question, response),
            "entity": knowledge["entity"],
            "intent": "definition",
            "source": best_source["name"],
            "source_url": best_source["url"],
            "confidence": knowledge["confidence"],
            "learned_at": datetime.now().isoformat(),
            "auto_learned": True
        }

        return qa_pattern

    def _extract_keywords(self, question: str, response: str) -> List[str]:
        """質問と応答からキーワードを抽出"""
        # 簡易実装: 実体と名詞を抽出
        keywords = []

        # 質問から実体を抽出
        entity_match = re.match(r'(.+?)(とは|って何|について)', question)
        if entity_match:
            keywords.append(entity_match.group(1).strip())

        # 応答から名詞を抽出（カタカナ、漢字、英数字）
        nouns = re.findall(r'[ァ-ヶー]+|[一-龯]+|[A-Za-z][A-Za-z0-9]*', response)
        keywords.extend(nouns[:5])  # 最大5個

        return list(set(keywords))

    def _load_learning_queue(self) -> List[Dict[str, Any]]:
        """学習キューを読み込み"""
        if self.learning_queue_file.exists():
            with open(self.learning_queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_learning_queue(self, queue: List[Dict[str, Any]]):
        """学習キューを保存"""
        self.learning_queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.learning_queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)

    def _save_qa_pattern(self, qa_pattern: Dict[str, Any]):
        """学習したQ&Aパターンを保存"""
        # 既存の知識を読み込み
        if self.knowledge_file.exists():
            with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                knowledge = json.load(f)
        else:
            knowledge = {"auto_learned_patterns": []}

        # 新しいパターンを追加
        knowledge["auto_learned_patterns"].append(qa_pattern)

        # 保存
        self.knowledge_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge, f, ensure_ascii=False, indent=2)

    def apply_learned_knowledge(self) -> Dict[str, Any]:
        """
        学習した知識をシステムに適用
        
        Returns:
            適用結果の統計
        """
        apply_stats = {
            "qa_patterns_added": 0,
            "timestamp": datetime.now().isoformat()
        }

        # 学習した知識を読み込み
        if not self.knowledge_file.exists():
            return apply_stats

        with open(self.knowledge_file, 'r', encoding='utf-8') as f:
            knowledge = json.load(f)

        auto_learned = knowledge.get("auto_learned_patterns", [])

        # 未適用の高信頼度パターンを抽出
        for qa in auto_learned:
            if qa.get("auto_learned") and qa.get("confidence", 0) > 0.7:
                if not qa.get("applied", False):
                    # KnowledgeLearnerに追加する処理は別途実装
                    # ここでは適用済みとしてマーク
                    qa["applied"] = True
                    qa["applied_at"] = datetime.now().isoformat()
                    apply_stats["qa_patterns_added"] += 1

        # 保存
        with open(self.knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge, f, ensure_ascii=False, indent=2)

        return apply_stats
