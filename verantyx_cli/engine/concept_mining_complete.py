#!/usr/bin/env python3
"""
Concept Mining - 完全実装

Claudeログから概念を実際に抽出する
TF-IDF的手法 + パターンマッチ + ルール生成
"""

from typing import List, Dict, Tuple, Set
from collections import Counter
import re
import hashlib
from datetime import datetime


class ProblemFeatureExtractor:
    """Problem特徴抽出器"""

    # エラーキーワード辞書
    ERROR_KEYWORDS = {
        "error", "エラー", "failed", "失敗", "cannot", "できない",
        "問題", "trouble", "issue", "bug", "バグ", "wrong", "incorrect"
    }

    # ドメインキーワード辞書
    DOMAIN_KEYWORDS = {
        "docker": ["docker", "container", "dockerfile", "image", "build"],
        "git": ["git", "commit", "push", "pull", "branch", "merge", "conflict"],
        "python": ["python", "pip", "import", "module", "pandas", "numpy", "pytest"],
        "javascript": ["javascript", "node", "npm", "react", "vue", "jest"],
        "database": ["database", "db", "sql", "postgres", "mysql", "mongodb"],
        "api": ["api", "endpoint", "request", "response", "http", "rest"],
        "web": ["html", "css", "browser", "dom", "selector"],
        "cloud": ["aws", "azure", "gcp", "cloud", "deploy", "deployment"]
    }

    # 問題タイプパターン
    PROBLEM_PATTERNS = {
        "build_error": ["build", "compile", "ビルド", "コンパイル"],
        "runtime_error": ["runtime", "execution", "実行"],
        "connection_error": ["connection", "connect", "接続"],
        "authentication_error": ["auth", "authentication", "認証", "login"],
        "configuration_error": ["config", "configuration", "設定"],
        "dependency_error": ["dependency", "依存", "module", "package"],
        "syntax_error": ["syntax", "構文"],
        "permission_error": ["permission", "権限", "access"]
    }

    def extract(self, user_input: str) -> Dict:
        """Problem特徴を抽出"""
        features = {
            "has_error": self._detect_error(user_input),
            "domain": self._detect_domain(user_input),
            "problem_type": self._detect_problem_type(user_input),
            "keywords": self._extract_keywords(user_input),
            "entities": self._extract_entities(user_input)
        }

        return features

    def _detect_error(self, text: str) -> bool:
        """エラーが含まれているか"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.ERROR_KEYWORDS)

    def _detect_domain(self, text: str) -> str:
        """ドメインを検出"""
        text_lower = text.lower()

        # 各ドメインのスコアを計算
        scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[domain] = score

        if scores:
            return max(scores, key=scores.get)

        return "general"

    def _detect_problem_type(self, text: str) -> str:
        """問題タイプを検出"""
        text_lower = text.lower()

        for ptype, keywords in self.PROBLEM_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                return ptype

        return "unknown"

    def _extract_keywords(self, text: str) -> List[str]:
        """重要キーワードを抽出（TF-IDF的）"""
        # 単語分割
        words = re.findall(r'\b\w+\b', text.lower())

        # ストップワード除去
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for"}
        words = [w for w in words if w not in stopwords and len(w) > 2]

        # 頻度カウント
        word_counts = Counter(words)

        # Top 5を返す
        return [word for word, _ in word_counts.most_common(5)]

    def _extract_entities(self, text: str) -> List[str]:
        """固有名詞を抽出（簡易）"""
        # 大文字で始まる単語
        entities = re.findall(r'\b[A-Z][a-zA-Z]+\b', text)

        # ファイル名
        files = re.findall(r'\b\w+\.\w+\b', text)

        return list(set(entities + files))


class SolutionStepExtractor:
    """Solution手順抽出器"""

    # アクション動詞辞書
    ACTION_VERBS = {
        "確認": "check",
        "チェック": "check",
        "実行": "execute",
        "試す": "try",
        "インストール": "install",
        "設定": "configure",
        "修正": "fix",
        "削除": "delete",
        "追加": "add",
        "更新": "update",
        "再起動": "restart",
        "検証": "verify",
        "テスト": "test",
        "デバッグ": "debug"
    }

    def extract(self, claude_response: str) -> Dict:
        """Solution手順を抽出"""
        result = {
            "steps": self._extract_steps(claude_response),
            "actions": self._extract_actions(claude_response),
            "commands": self._extract_commands(claude_response),
            "recommendations": self._extract_recommendations(claude_response)
        }

        return result

    def _extract_steps(self, text: str) -> List[str]:
        """手順を抽出"""
        steps = []

        # 番号付きリスト（1. 2. 3. or １．２．３．）
        numbered = re.findall(r'(?:^|\n)\s*(?:\d+[.．)）]|[①-⑩])\s*(.+?)(?=\n|$)', text)
        steps.extend(numbered)

        # 箇条書き（・- * など）
        bullets = re.findall(r'(?:^|\n)\s*[・\-\*]\s*(.+?)(?=\n|$)', text)
        steps.extend(bullets)

        # 順序を示す言葉（まず、次に、最後に）
        sequential = re.findall(r'(?:まず|次に|その後|最後に)[、,]\s*(.+?)(?:[。\n]|$)', text)
        steps.extend(sequential)

        # 文ごとに分割してアクション動詞を含む文を抽出
        sentences = re.split(r'[。\n]+', text)
        for sentence in sentences:
            if any(verb in sentence for verb in self.ACTION_VERBS.keys()):
                if sentence.strip() and sentence.strip() not in steps:
                    steps.append(sentence.strip())

        # 重複除去 + 長さ制限
        seen = set()
        unique_steps = []
        for step in steps:
            step = step.strip()
            if step and step not in seen and len(step) > 5:
                seen.add(step)
                unique_steps.append(step)

        return unique_steps[:10]  # 最大10ステップ

    def _extract_actions(self, text: str) -> List[str]:
        """アクションを抽出"""
        actions = []

        for jp_verb, en_verb in self.ACTION_VERBS.items():
            if jp_verb in text:
                actions.append(en_verb)

        # 重複除去
        return list(set(actions))

    def _extract_commands(self, text: str) -> List[str]:
        """コマンドを抽出"""
        # コマンドライン（`...` or ```...```）
        commands = re.findall(r'`([^`]+)`', text)

        # コマンド形式（docker ..., git ..., npm ...）
        cmd_patterns = re.findall(r'\b(docker|git|npm|pip|python|node)\s+[\w\-]+[^\n]*', text)

        return commands + cmd_patterns

    def _extract_recommendations(self, text: str) -> List[str]:
        """推奨事項を抽出"""
        # 「〜してください」「〜しましょう」
        recommendations = re.findall(r'(.+?(?:してください|しましょう|します))', text)

        return [rec.strip() for rec in recommendations if len(rec.strip()) > 5]


class ConceptAbstractor:
    """概念抽象化器"""

    def abstract(self, problem_features: Dict, solution_data: Dict) -> Dict:
        """Problem + Solution → Abstract Concept"""

        # 概念名を生成
        concept_name = self._generate_concept_name(
            problem_features['domain'],
            problem_features['problem_type'],
            solution_data['actions']
        )

        # ルールを生成
        rule = self._generate_rule(solution_data['steps'], solution_data['actions'])

        # 入力/出力を定義
        inputs = self._define_inputs(problem_features)
        outputs = self._define_outputs(solution_data)

        concept = {
            "name": concept_name,
            "domain": problem_features['domain'],
            "problem_type": problem_features['problem_type'],
            "rule": rule,
            "inputs": inputs,
            "outputs": outputs,
            "examples": [],
            "confidence": 0.5,
            "use_count": 0
        }

        return concept

    def _generate_concept_name(self, domain: str, problem_type: str, actions: List[str]) -> str:
        """概念名を生成"""
        # domain_problemtype_action
        action_str = "_".join(actions[:2]) if actions else "recovery"
        name = f"{domain}_{problem_type}_{action_str}"

        # 正規化
        name = re.sub(r'[^\w_]', '', name)
        return name.lower()

    def _generate_rule(self, steps: List[str], actions: List[str]) -> str:
        """ルールを生成 (A → B → C形式)"""
        if not actions:
            return "unknown"

        # アクションを順序化
        action_sequence = []

        # ステップからアクションを抽出
        for step in steps[:5]:  # 最大5ステップ
            for action in ["check", "fix", "verify", "install", "configure", "execute", "test"]:
                if action in actions and action not in action_sequence:
                    if action in step.lower() or self._matches_step(action, step):
                        action_sequence.append(action)

        # 不足分を補完
        if "check" not in action_sequence and actions:
            action_sequence.insert(0, "check")
        if "verify" not in action_sequence and len(action_sequence) > 1:
            action_sequence.append("verify")

        # 最小3ステップ
        while len(action_sequence) < 3 and actions:
            added = False
            for action in actions:
                if action not in action_sequence:
                    action_sequence.append(action)
                    added = True
                    break
            if not added:  # No more actions to add
                break

        return " → ".join(action_sequence[:5])

    def _matches_step(self, action: str, step: str) -> bool:
        """アクションがステップにマッチするか"""
        action_keywords = {
            "check": ["確認", "チェック", "見る", "調べる"],
            "fix": ["修正", "直す", "変更", "編集"],
            "verify": ["検証", "確かめる", "テスト"],
            "install": ["インストール", "追加"],
            "configure": ["設定", "構成"],
            "execute": ["実行", "起動", "動かす"],
            "test": ["テスト", "試す"]
        }

        keywords = action_keywords.get(action, [])
        return any(kw in step for kw in keywords)

    def _define_inputs(self, problem_features: Dict) -> List[str]:
        """入力を定義"""
        inputs = [
            f"domain:{problem_features['domain']}",
            f"problem_type:{problem_features['problem_type']}"
        ]

        # キーワードを追加
        for kw in problem_features['keywords'][:3]:
            inputs.append(f"keyword:{kw}")

        return inputs

    def _define_outputs(self, solution_data: Dict) -> List[str]:
        """出力を定義"""
        outputs = [
            f"steps:{len(solution_data['steps'])}",
            "success:boolean"
        ]

        # アクション追加
        for action in solution_data['actions'][:3]:
            outputs.append(f"action:{action}")

        return outputs


class RealConceptMiner:
    """実際に動くConcept Miner"""

    def __init__(self):
        self.problem_extractor = ProblemFeatureExtractor()
        self.solution_extractor = SolutionStepExtractor()
        self.abstractor = ConceptAbstractor()

        # 概念データベース
        self.concepts: Dict[str, Dict] = {}

    def mine(self, user_input: str, claude_response: str) -> Tuple[Dict, bool]:
        """
        概念をマイニング

        Returns:
            (concept, is_new)
        """
        # 1. Problem特徴抽出
        problem_features = self.problem_extractor.extract(user_input)

        # 2. Solution手順抽出
        solution_data = self.solution_extractor.extract(claude_response)

        # 3. 抽象化
        abstract_concept = self.abstractor.abstract(problem_features, solution_data)

        # 4. 類似概念検索
        similar = self._find_similar_concept(abstract_concept)

        if similar:
            # 既存概念を強化
            self._strengthen_concept(similar, abstract_concept)
            return similar, False
        else:
            # 新規登録
            concept_id = self._generate_id(abstract_concept['name'])
            abstract_concept['id'] = concept_id
            abstract_concept['created_at'] = datetime.now().isoformat()

            self.concepts[concept_id] = abstract_concept
            return abstract_concept, True

    def _find_similar_concept(self, new_concept: Dict) -> Dict:
        """類似概念を検索"""
        # ドメイン + 問題タイプが一致
        for concept in self.concepts.values():
            if (concept['domain'] == new_concept['domain'] and
                concept['problem_type'] == new_concept['problem_type']):

                # ルールの類似度
                similarity = self._calculate_rule_similarity(
                    concept['rule'],
                    new_concept['rule']
                )

                if similarity > 0.6:
                    return concept

        return None

    def _calculate_rule_similarity(self, rule1: str, rule2: str) -> float:
        """ルールの類似度を計算"""
        steps1 = set(rule1.split(" → "))
        steps2 = set(rule2.split(" → "))

        if not steps1 or not steps2:
            return 0.0

        intersection = steps1 & steps2
        union = steps1 | steps2

        return len(intersection) / len(union)

    def _strengthen_concept(self, existing: Dict, new_concept: Dict):
        """既存概念を強化"""
        # 使用回数を増加
        existing['use_count'] += 1

        # 信頼度を更新（最大1.0）
        existing['confidence'] = min(1.0, existing['confidence'] + 0.1)

        # 例を追加
        if 'examples' not in existing:
            existing['examples'] = []

        existing['examples'].append({
            "inputs": new_concept['inputs'],
            "outputs": new_concept['outputs'],
            "timestamp": datetime.now().isoformat()
        })

        # 最大10例まで
        if len(existing['examples']) > 10:
            existing['examples'] = existing['examples'][-10:]

    def _generate_id(self, name: str) -> str:
        """概念IDを生成"""
        hash_obj = hashlib.md5(name.encode())
        return f"concept_{hash_obj.hexdigest()[:8]}"

    def get_statistics(self) -> Dict:
        """統計を取得"""
        return {
            "total_concepts": len(self.concepts),
            "by_domain": self._count_by_domain(),
            "avg_confidence": self._average_confidence()
        }

    def _count_by_domain(self) -> Dict[str, int]:
        """ドメイン別カウント"""
        counts = Counter(c['domain'] for c in self.concepts.values())
        return dict(counts)

    def _average_confidence(self) -> float:
        """平均信頼度"""
        if not self.concepts:
            return 0.0

        total = sum(c['confidence'] for c in self.concepts.values())
        return total / len(self.concepts)


# VMプロセッサとして登録
def register_real_miner_to_vm(vm):
    """Real Concept MinerをVMに登録"""
    miner = RealConceptMiner()

    def mine_concept(user_input: str, claude_response: str) -> Dict:
        """概念をマイニング"""
        concept, is_new = miner.mine(user_input, claude_response)
        return {
            "concept": concept,
            "is_new": is_new
        }

    vm.register_processor("実際の概念マイニング", mine_concept)
    vm.register_processor("概念統計取得", lambda: miner.get_statistics())

    print("✓ Real Concept Miner registered")

    return miner
