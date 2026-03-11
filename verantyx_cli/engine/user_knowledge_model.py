#!/usr/bin/env python3
"""
User Knowledge Model - 個人専用AI基盤

Verantyxの最終目標:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Personal AI - ユーザーごとに進化するAI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UserModel = {
    skills: ["Python", "Docker", "ML"],
    tools: ["git", "pytest", "numpy"],
    domains: ["data_analysis", "web_dev"],
    preferences: {
        code_style: "detailed",
        response_style: "concise"
    },
    learning_history: [...]
}

このモデルに基づいて:
    - Claude回答を個人最適化
    - .jcrossプログラムを個人最適化
    - 推論を個人最適化
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

from .task_structure_extractor import TaskStructure


@dataclass
class UserProfile:
    """ユーザープロファイル"""
    user_id: str

    # スキル・知識
    skills: Dict[str, float] = field(default_factory=dict)  # skill -> proficiency
    tools: Dict[str, int] = field(default_factory=dict)     # tool -> usage_count
    domains: Dict[str, float] = field(default_factory=dict)  # domain -> familiarity

    # 選好
    preferences: Dict[str, Any] = field(default_factory=dict)

    # 統計
    total_interactions: int = 0
    success_rate: float = 0.5

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class UserKnowledgeModel:
    """
    ユーザー知識モデル

    機能:
    1. ユーザープロファイル管理
    2. スキル・ツール使用頻度追跡
    3. ドメイン専門性推定
    4. 個人最適化された推論
    """

    def __init__(self, user_id: str, storage_path: Optional[Path] = None):
        self.user_id = user_id
        self.storage_path = storage_path or Path(f".verantyx/users/{user_id}.json")

        self.profile = self._load_or_create_profile()

    def _load_or_create_profile(self) -> UserProfile:
        """プロファイルを読み込みまたは作成"""
        if self.storage_path.exists():
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return UserProfile(
                    user_id=data["user_id"],
                    skills=data.get("skills", {}),
                    tools=data.get("tools", {}),
                    domains=data.get("domains", {}),
                    preferences=data.get("preferences", {}),
                    total_interactions=data.get("total_interactions", 0),
                    success_rate=data.get("success_rate", 0.5),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", "")
                )

        return UserProfile(user_id=self.user_id)

    def update_from_task(self, task: TaskStructure):
        """タスクからプロファイルを更新"""
        # ドメイン更新
        domain = task.domain
        if domain != "general":
            self.profile.domains[domain] = self.profile.domains.get(domain, 0.0) + 0.1

        # ツール更新
        for tool in task.tools_used:
            self.profile.tools[tool] = self.profile.tools.get(tool, 0) + 1

        # スキル推定
        for concept in task.concepts:
            self.profile.skills[concept] = self.profile.skills.get(concept, 0.0) + 0.05

        # 統計更新
        self.profile.total_interactions += 1
        if task.success:
            success_count = int(self.profile.success_rate * (self.profile.total_interactions - 1))
            self.profile.success_rate = (success_count + 1) / self.profile.total_interactions

        self.profile.updated_at = datetime.now().isoformat()

        self.save()

    def save(self):
        """プロファイルを保存"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump({
                "user_id": self.profile.user_id,
                "skills": self.profile.skills,
                "tools": self.profile.tools,
                "domains": self.profile.domains,
                "preferences": self.profile.preferences,
                "total_interactions": self.profile.total_interactions,
                "success_rate": self.profile.success_rate,
                "created_at": self.profile.created_at,
                "updated_at": self.profile.updated_at
            }, f, ensure_ascii=False, indent=2)

    def get_expertise_level(self, domain: str) -> float:
        """ドメインの専門度を取得"""
        return self.profile.domains.get(domain, 0.0)

    def get_preferred_tools(self, top_n: int = 5) -> List[str]:
        """よく使うツールを取得"""
        sorted_tools = sorted(
            self.profile.tools.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [tool for tool, _ in sorted_tools[:top_n]]
