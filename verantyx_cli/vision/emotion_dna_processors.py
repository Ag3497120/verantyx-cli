#!/usr/bin/env python3
"""
Emotion DNA Processors
感情DNAシステムのPythonプロセッサ

Gemini的洞察の実装:
1. ホメオスタシスの閾値
2. 神経伝達物質の極性
3. 全同調への強制割り込みルール
"""

from typing import Dict, Any, List, Optional


class EmotionDNASystem:
    """
    感情DNAシステム

    感情 = システム全体のリソース配分パターン
    """

    def __init__(self):
        """Initialize"""
        # 神経伝達物質
        self.neurotransmitters = {
            "dopamine": 0.0,        # ドーパミン（快）
            "noradrenaline": 0.0,   # ノルアドレナリン（不快・緊張）
            "serotonin": 0.5        # セロトニン（安心・安定）
        }

        # 現在の感情
        self.current_emotion = {
            "dominant_emotion": "none",
            "intensity": 0.0,
            "resource_allocation": self._default_resources(),
            "node_synchronization": "normal_mode",
            "color": "colorless"
        }

        # 感情割り込みルール
        self.emotion_rules = {
            "fear": {
                "priority": 10,
                "resources": {
                    "flee": 1.0,
                    "learn": 0.0,
                    "explore": 0.0,
                    "predict": 0.1,
                    "memory": 1.0
                },
                "sync": "flee_mode",
                "color": "red"
            },
            "anger": {
                "priority": 9,
                "resources": {
                    "attack": 1.0,
                    "learn": 0.2,
                    "explore": 0.3,
                    "predict": 0.5,
                    "memory": 0.8
                },
                "sync": "attack_mode",
                "color": "dark_red"
            },
            "joy": {
                "priority": 5,
                "resources": {
                    "explore": 1.0,
                    "learn": 1.0,
                    "predict": 0.8,
                    "memory": 0.9,
                    "flee": 0.0
                },
                "sync": "explore_learn_mode",
                "color": "yellow"
            },
            "sadness": {
                "priority": 6,
                "resources": {
                    "explore": 0.1,
                    "learn": 0.3,
                    "predict": 0.5,
                    "memory": 1.0,
                    "rest": 1.0
                },
                "sync": "energy_save_mode",
                "color": "blue"
            },
            "calm": {
                "priority": 3,
                "resources": {
                    "explore": 0.6,
                    "learn": 0.7,
                    "predict": 0.7,
                    "memory": 0.6,
                    "rest": 0.5
                },
                "sync": "balanced_mode",
                "color": "green"
            },
            "curiosity": {
                "priority": 7,
                "resources": {
                    "explore": 1.0,
                    "learn": 0.9,
                    "predict": 0.8,
                    "memory": 0.7,
                    "flee": 0.0
                },
                "sync": "active_exploration_mode",
                "color": "orange"
            }
        }

    def _default_resources(self) -> Dict[str, float]:
        """デフォルトのリソース配分"""
        return {
            "explore": 0.5,
            "learn": 0.5,
            "predict": 0.5,
            "memory": 0.5,
            "rest": 0.5
        }

    def release_dopamine(self, amount: float, reason: str = ""):
        """
        ドーパミン放出（快）

        Args:
            amount: 放出量 (0.0-1.0)
            reason: 理由
        """
        self.neurotransmitters["dopamine"] += amount
        self.neurotransmitters["dopamine"] = min(1.0, self.neurotransmitters["dopamine"])

    def release_noradrenaline(self, amount: float, reason: str = ""):
        """
        ノルアドレナリン放出（不快・緊張）

        Args:
            amount: 放出量 (0.0-1.0)
            reason: 理由
        """
        self.neurotransmitters["noradrenaline"] += amount
        self.neurotransmitters["noradrenaline"] = min(1.0, self.neurotransmitters["noradrenaline"])

    def release_serotonin(self, amount: float, reason: str = ""):
        """
        セロトニン放出（安心・安定）

        Args:
            amount: 放出量 (0.0-1.0)
            reason: 理由
        """
        self.neurotransmitters["serotonin"] += amount
        self.neurotransmitters["serotonin"] = min(1.0, self.neurotransmitters["serotonin"])

    def decay_neurotransmitters(self, decay_rate: float = 0.1):
        """
        神経伝達物質の減衰

        Args:
            decay_rate: 減衰率
        """
        self.neurotransmitters["dopamine"] *= (1.0 - decay_rate)
        self.neurotransmitters["noradrenaline"] *= (1.0 - decay_rate)
        # セロトニンは0.5に戻る傾向
        if self.neurotransmitters["serotonin"] > 0.5:
            self.neurotransmitters["serotonin"] -= decay_rate * 0.5
        else:
            self.neurotransmitters["serotonin"] += decay_rate * 0.5

    def determine_emotion(
        self,
        physiological_state: Dict[str, Any],
        cognitive_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        感情を判定（強制割り込み）

        Args:
            physiological_state: 生理状態
            cognitive_state: 認知状態

        Returns:
            現在の感情
        """
        candidates = []

        # 恐怖チェック
        pain = physiological_state.get("pain", 0.0)
        critical_deviation = physiological_state.get("critical_deviation", False)

        if pain > 50.0 or critical_deviation:
            candidates.append({
                "emotion": "fear",
                "priority": 10,
                "intensity": 1.0
            })

        # 怒りチェック
        total_discomfort = cognitive_state.get("total_discomfort", 0.0)
        resolution_failures = cognitive_state.get("resolution_failures", 0)

        if total_discomfort > 0.8 and resolution_failures > 3:
            candidates.append({
                "emotion": "anger",
                "priority": 9,
                "intensity": 0.9
            })

        # 喜びチェック
        dopamine = self.neurotransmitters["dopamine"]
        if dopamine > 0.8 and total_discomfort < 0.2:
            candidates.append({
                "emotion": "joy",
                "priority": 5,
                "intensity": dopamine
            })

        # 悲しみチェック
        energy = physiological_state.get("energy", 100.0)
        if total_discomfort > 0.6 and energy < 30.0:
            candidates.append({
                "emotion": "sadness",
                "priority": 6,
                "intensity": 0.7
            })

        # 安心チェック
        serotonin = self.neurotransmitters["serotonin"]
        all_deviation = physiological_state.get("all_deviation", 0.0)
        if serotonin > 0.5 and all_deviation < 0.1:
            candidates.append({
                "emotion": "calm",
                "priority": 3,
                "intensity": serotonin
            })

        # 好奇心チェック
        novelty_discomfort = cognitive_state.get("novelty_discomfort", 0.0)
        if novelty_discomfort > 0.5 and energy > 50.0:
            candidates.append({
                "emotion": "curiosity",
                "priority": 7,
                "intensity": novelty_discomfort
            })

        # 優先度が最も高い感情を選択
        if not candidates:
            # ニュートラル
            self.current_emotion = {
                "dominant_emotion": "none",
                "intensity": 0.0,
                "resource_allocation": self._default_resources(),
                "node_synchronization": "normal_mode",
                "color": "colorless"
            }
            return self.current_emotion

        # 最高優先度
        dominant = max(candidates, key=lambda x: x["priority"])

        # 感情を適用
        self._apply_emotion(dominant["emotion"], dominant["intensity"])

        return self.current_emotion

    def _apply_emotion(self, emotion_name: str, intensity: float):
        """
        感情を適用（リソース配分の変更）

        Args:
            emotion_name: 感情名
            intensity: 強度
        """
        if emotion_name not in self.emotion_rules:
            return

        rule = self.emotion_rules[emotion_name]

        self.current_emotion = {
            "dominant_emotion": emotion_name,
            "intensity": intensity,
            "resource_allocation": rule["resources"],
            "node_synchronization": rule["sync"],
            "color": rule["color"]
        }

    def add_color_to_memory(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """
        記憶に「色」を付ける

        Args:
            experience: 経験

        Returns:
            色付き経験
        """
        experience["color"] = self.current_emotion["color"]
        experience["emotion"] = self.current_emotion["dominant_emotion"]
        experience["emotion_intensity"] = self.current_emotion["intensity"]
        experience["neurotransmitters"] = self.neurotransmitters.copy()

        return experience

    def process_event(
        self,
        prediction_error: float,
        similar_experiences_count: int,
        sync_degree: float,
        discomfort_decreased: bool = False,
        new_pattern_found: bool = False
    ):
        """
        イベント処理（神経伝達物質の放出）

        Args:
            prediction_error: 予測誤差
            similar_experiences_count: 類似経験数
            sync_degree: 同調度
            discomfort_decreased: 不快感が減少したか
            new_pattern_found: 新パターン発見
        """
        # ドーパミン放出条件
        if prediction_error < 0.05:
            self.release_dopamine(1.0, "prediction_success")

        if sync_degree > 0.8:
            self.release_dopamine(0.8, "synchronization_success")

        if discomfort_decreased:
            self.release_dopamine(1.0, "discomfort_resolved")

        if new_pattern_found:
            self.release_dopamine(0.6, "new_discovery")

        # ノルアドレナリン放出条件
        if prediction_error > 0.5:
            self.release_noradrenaline(1.0, "prediction_failure")

        if similar_experiences_count == 0:
            self.release_noradrenaline(0.8, "novel_unknown")

        # セロトニン放出条件
        if similar_experiences_count >= 5 and prediction_error < 0.1:
            self.release_serotonin(0.6, "repeated_synchronization")

    def get_status(self) -> Dict[str, Any]:
        """状態を取得"""
        return {
            "current_emotion": self.current_emotion,
            "neurotransmitters": self.neurotransmitters
        }

    def get_emotion_color_name(self) -> str:
        """感情の色の名前を取得"""
        color_map = {
            "red": "赤（警告）",
            "dark_red": "暗赤（憤怒）",
            "yellow": "黄（明るい）",
            "blue": "青（沈静）",
            "green": "緑（安定）",
            "orange": "オレンジ（好奇）",
            "colorless": "無色"
        }
        return color_map.get(self.current_emotion["color"], "不明")

    def get_emotion_japanese(self) -> str:
        """感情の日本語名を取得"""
        emotion_map = {
            "fear": "恐怖",
            "anger": "怒り",
            "joy": "喜び",
            "sadness": "悲しみ",
            "calm": "安心",
            "curiosity": "好奇心",
            "none": "なし"
        }
        return emotion_map.get(self.current_emotion["dominant_emotion"], "不明")
