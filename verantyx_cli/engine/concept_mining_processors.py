#!/usr/bin/env python3
"""
Concept Mining Processors

concept_mining.jcrossで使用されるプロセッサ群
"""

from typing import List, Any, Dict
import re
import hashlib
from datetime import datetime


class ConceptMiningProcessors:
    """Concept Mining用のプロセッサ集"""

    @staticmethod
    def 文分割(text: str) -> List[str]:
        """テキストを文に分割"""
        # 句点・改行で分割
        sentences = re.split(r'[。\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def フィルタ(sentences: List[str], keywords: str) -> List[str]:
        """キーワードを含む文をフィルタ"""
        keyword_pattern = keywords.replace("|", "|")
        results = []

        for sentence in sentences:
            if re.search(keyword_pattern, sentence, re.IGNORECASE):
                results.append(sentence)

        return results

    @staticmethod
    def ルールパターン生成(steps: List[str]) -> str:
        """
        手順から抽象ルールパターンを生成

        例: ["確認する", "修正する", "再実行する"]
            → "check → fix → verify"
        """
        if not steps:
            return "unknown"

        # 日本語 → 英語抽象化マップ
        action_map = {
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
            "再": "re",
            "検証": "verify"
        }

        abstract_steps = []
        for step in steps:
            # アクション抽出
            for jp, en in action_map.items():
                if jp in step:
                    abstract_steps.append(en)
                    break
            else:
                abstract_steps.append("action")

        # 重複除去
        unique_steps = []
        for step in abstract_steps:
            if not unique_steps or unique_steps[-1] != step:
                unique_steps.append(step)

        return " → ".join(unique_steps[:5])  # 最大5ステップ

    @staticmethod
    def ID生成(concept_name: str) -> str:
        """概念IDを生成"""
        # ハッシュベース
        hash_obj = hashlib.md5(concept_name.encode())
        return f"concept_{hash_obj.hexdigest()[:8]}"

    @staticmethod
    def Concept登録(concept_id: str, name: str, rule: str, domain: str) -> Dict:
        """
        概念をConcept空間に登録

        注: 実際にはVMのCross空間に保存される
        """
        concept_data = {
            "id": concept_id,
            "name": name,
            "rule": rule,
            "domain": domain,
            "confidence": 0.5,
            "use_count": 0,
            "created_at": datetime.now().isoformat(),
            "examples": []
        }

        return concept_data

    @staticmethod
    def インデックス追加(concept_id: str, domain: str) -> bool:
        """ドメイン別インデックスに追加"""
        # 注: VMが実際のインデックス管理を行う
        return True

    @staticmethod
    def 信頼度更新(concept: Dict, delta: float) -> float:
        """概念の信頼度を更新"""
        if isinstance(concept, dict):
            old_confidence = concept.get("confidence", 0.5)
            new_confidence = min(1.0, old_confidence + delta)
            concept["confidence"] = new_confidence
            return new_confidence

        return 0.5

    @staticmethod
    def 例追加(existing_concept: Dict, new_concept: Any) -> bool:
        """概念に例を追加"""
        if isinstance(existing_concept, dict):
            if "examples" not in existing_concept:
                existing_concept["examples"] = []

            existing_concept["examples"].append({
                "data": str(new_concept),
                "timestamp": datetime.now().isoformat()
            })

            # 最大10例まで保持
            if len(existing_concept["examples"]) > 10:
                existing_concept["examples"] = existing_concept["examples"][-10:]

            return True

        return False

    @staticmethod
    def カウンター更新(concept_id: str) -> int:
        """使用カウンターを更新（VMが管理）"""
        # 注: 実際はVMのCross空間から取得・更新
        return 1

    @staticmethod
    def タイムスタンプ更新(concept_id: str) -> str:
        """最終使用時刻を更新"""
        return datetime.now().isoformat()


def register_to_vm(vm):
    """
    VMにプロセッサを登録
    """
    processors = ConceptMiningProcessors()

    vm.register_processor("文分割", processors.文分割)
    vm.register_processor("フィルタ", processors.フィルタ)
    vm.register_processor("ルールパターン生成", processors.ルールパターン生成)
    vm.register_processor("ID生成", processors.ID生成)
    vm.register_processor("Concept登録", processors.Concept登録)
    vm.register_processor("インデックス追加", processors.インデックス追加)
    vm.register_processor("信頼度更新", processors.信頼度更新)
    vm.register_processor("例追加", processors.例追加)
    vm.register_processor("カウンター更新", processors.カウンター更新)
    vm.register_processor("タイムスタンプ更新", processors.タイムスタンプ更新)

    print("✓ Concept Mining processors registered")
