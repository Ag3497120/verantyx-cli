#!/usr/bin/env python3
"""
Developmental Stages Processors
発達段階システムのPythonプロセッサ

JCrossの発達段階ロジックを実行する最小限のブリッジ
"""

import random
import math
from typing import Dict, Any, Optional, List
from datetime import datetime


class DevelopmentalStageSystem:
    """
    発達段階システム

    0歳 → 1歳 → 3歳 → 7歳 → 18歳（成人）
    記憶と経験が成長とともにグレードアップ
    """

    def __init__(self, growth_speed: float = 1000.0):
        """
        Initialize developmental system

        Args:
            growth_speed: 成長速度（1.0=リアルタイム, 1000.0=1000倍速）
        """
        # 発達段階定義
        self.stages = {
            "0歳_新生児": {
                "age_range": [0, 1],
                "mobility": "寝たきり",
                "spatial_memory": False,
                "memory_format": "undefined_buffer",
                "experience_format": "受動的観察",
                "description": "視覚のみ、位置概念なし"
            },
            "1歳_立位": {
                "age_range": [1, 3],
                "mobility": "立てる・つかまり歩き",
                "spatial_memory": True,
                "memory_format": "spatial_tagged",
                "experience_format": "探索的観察",
                "description": "ランダムな3D位置を付与"
            },
            "3歳_歩行": {
                "age_range": [3, 7],
                "mobility": "歩き回る・走る",
                "spatial_memory": True,
                "memory_format": "trajectory_based",
                "experience_format": "能動的探索",
                "description": "移動軌跡を記憶"
            },
            "7歳_学童期": {
                "age_range": [7, 18],
                "mobility": "複雑な運動",
                "spatial_memory": True,
                "memory_format": "categorical",
                "experience_format": "概念的学習",
                "description": "カテゴリ化、因果推論"
            },
            "18歳_成人": {
                "age_range": [18, float('inf')],
                "mobility": "完全制御",
                "spatial_memory": True,
                "memory_format": "abstract_conceptual",
                "experience_format": "メタ認知",
                "description": "抽象思考、仮説検証"
            }
        }

        # 現在の発達状態
        self.state = {
            "current_age": 0.0,
            "current_stage": "0歳_新生児",
            "experience_time": 0.0,
            "growth_speed": growth_speed
        }

        # 記憶
        self.memory = {
            "last_position": None,
            "category_centers": [],
            "experience_count": 0
        }

        print(f"🧠 発達段階システム初期化")
        print(f"   成長速度: {growth_speed}x")
        print()

    def update_age(self, elapsed_seconds: float) -> str:
        """
        年齢を更新

        Args:
            elapsed_seconds: 経過秒数

        Returns:
            現在の発達段階
        """
        # 経験時間を加算
        self.state["experience_time"] += elapsed_seconds

        # 年齢を計算（成長速度を考慮）
        seconds_per_year = 365.25 * 24 * 3600
        elapsed_years = (self.state["experience_time"] * self.state["growth_speed"]) / seconds_per_year
        self.state["current_age"] = elapsed_years

        # 発達段階を更新
        if self.state["current_age"] >= 18:
            self.state["current_stage"] = "18歳_成人"
        elif self.state["current_age"] >= 7:
            self.state["current_stage"] = "7歳_学童期"
        elif self.state["current_age"] >= 3:
            self.state["current_stage"] = "3歳_歩行"
        elif self.state["current_age"] >= 1:
            self.state["current_stage"] = "1歳_立位"
        else:
            self.state["current_stage"] = "0歳_新生児"

        return self.state["current_stage"]

    def add_spatial_memory(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """
        空間記憶を付与（1歳以降）

        Args:
            experience: 経験データ

        Returns:
            空間記憶が付与された経験
        """
        stage_info = self.stages[self.state["current_stage"]]

        if not stage_info["spatial_memory"]:
            # 0歳 - 空間記憶なし
            return experience

        # 1歳以降 - 空間記憶を付与
        if self.state["current_stage"] == "1歳_立位":
            # ランダムな3D位置（立位の視点から）
            experience["spatial"] = {
                "X": random.uniform(-100, 100),
                "Y": random.uniform(80, 150),  # 立った目線
                "Z": random.uniform(-100, 100),
                "type": "random_position"
            }

        elif self.state["current_stage"] == "3歳_歩行":
            # 移動軌跡ベース
            if self.memory["last_position"] is None:
                self.memory["last_position"] = {"X": 0, "Y": 100, "Z": 0}

            # 移動
            movement = {
                "X": random.uniform(-50, 50),
                "Y": random.uniform(-10, 10),
                "Z": random.uniform(-50, 50)
            }

            new_position = {
                "X": self.memory["last_position"]["X"] + movement["X"],
                "Y": self.memory["last_position"]["Y"] + movement["Y"],
                "Z": self.memory["last_position"]["Z"] + movement["Z"]
            }

            experience["spatial"] = new_position
            experience["trajectory"] = movement
            self.memory["last_position"] = new_position

        else:
            # 7歳以降 - 概念的空間
            experience["spatial"] = {
                "X": random.uniform(-200, 200),
                "Y": random.uniform(0, 300),
                "Z": random.uniform(-200, 200),
                "location": "undefined",
                "category": "unclassified"
            }

        return experience

    def upgrade_memory(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """
        記憶形式をアップグレード

        Args:
            experience: 古い経験

        Returns:
            アップグレードされた経験
        """
        stage_info = self.stages[self.state["current_stage"]]
        memory_format = stage_info["memory_format"]

        new_experience = experience.copy()

        if memory_format == "undefined_buffer":
            # 0歳 - そのまま
            return new_experience

        elif memory_format == "spatial_tagged":
            # 1歳 - 空間タグ追加
            new_experience = self.add_spatial_memory(new_experience)

        elif memory_format == "trajectory_based":
            # 3歳 - 軌跡追加
            new_experience = self.add_spatial_memory(new_experience)
            new_experience["sequence"] = self.memory["experience_count"]

        elif memory_format == "categorical":
            # 7歳 - カテゴリ追加
            new_experience = self.add_spatial_memory(new_experience)
            # カテゴリは後で自動分類
            new_experience["category"] = None
            new_experience["concept"] = None

        else:
            # 18歳 - 抽象概念
            new_experience = self.add_spatial_memory(new_experience)
            new_experience["category"] = None
            new_experience["concept"] = None
            new_experience["causal_relations"] = []
            new_experience["self_evaluation"] = None

        self.memory["experience_count"] += 1
        return new_experience

    def get_experience_mode(self, tension: float = 0.5) -> Dict[str, Any]:
        """
        経験処理方法を取得

        Args:
            tension: 緊張度（0-1）

        Returns:
            経験処理方法
        """
        stage_info = self.stages[self.state["current_stage"]]
        experience_format = stage_info["experience_format"]

        if experience_format == "受動的観察":
            # 0歳 - ただ見るだけ
            return {
                "mode": "passive",
                "action": None,
                "interest": 0.5
            }

        elif experience_format == "探索的観察":
            # 1歳 - 興味のあるものに注目
            return {
                "mode": "exploratory",
                "action": "focus" if tension > 0.3 else None,
                "interest": tension
            }

        elif experience_format == "能動的探索":
            # 3歳 - 自分から動いて確認
            return {
                "mode": "active_exploration",
                "action": "move_and_verify" if tension > 0.3 else "compare_with_memory",
                "interest": tension,
                "movement_plan": "approach" if tension > 0.5 else None
            }

        elif experience_format == "概念的学習":
            # 7歳 - カテゴリと概念で理解
            return {
                "mode": "conceptual_learning",
                "action": "category_inference",
                "interest": tension,
                "hypothesis": f"category_pattern"
            }

        else:
            # 18歳 - メタ認知
            return {
                "mode": "metacognition",
                "action": "hypothesis_testing",
                "interest": tension,
                "hypothesis": "abstract_pattern",
                "self_evaluation": "needs_more_data" if tension > 0.5 else "understood",
                "plan": "explore_unknown"
            }

    def get_status(self) -> Dict[str, Any]:
        """発達状態を取得"""
        stage_info = self.stages[self.state["current_stage"]]

        return {
            "年齢": self.state["current_age"],
            "段階": self.state["current_stage"],
            "経験時間_秒": self.state["experience_time"],
            "運動能力": stage_info["mobility"],
            "空間記憶": stage_info["spatial_memory"],
            "記憶形式": stage_info["memory_format"],
            "経験形式": stage_info["experience_format"],
            "説明": stage_info["description"],
            "総経験数": self.memory["experience_count"]
        }

    def print_status(self):
        """発達状態を表示"""
        status = self.get_status()

        print()
        print("=" * 80)
        print("👶 発達段階ステータス")
        print("=" * 80)
        print()
        print(f"年齢: {status['年齢']:.2f}歳")
        print(f"段階: {status['段階']}")
        print(f"運動能力: {status['運動能力']}")
        print(f"空間記憶: {'有効' if status['空間記憶'] else '無効'}")
        print(f"記憶形式: {status['記憶形式']}")
        print(f"経験形式: {status['経験形式']}")
        print(f"説明: {status['説明']}")
        print(f"総経験数: {status['総経験数']}")
        print()
        print("=" * 80)
        print()
