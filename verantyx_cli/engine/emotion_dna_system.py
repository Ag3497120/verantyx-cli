#!/usr/bin/env python3
"""
Emotion DNA System (Cross Structure Implementation)
感情DNAシステム（Cross構造実装）

Phase 3: 感情DNA統合
- emotion_dna_cross.jcrossを実際に動かす
- 3層構造（ホメオスタシス → 神経伝達物質 → 感情）をCross構造として処理
- 全ノードへの強制割り込みを実装
"""

from typing import Dict, Any, Optional
import numpy as np
from pathlib import Path

from jcross_interpreter import JCrossInterpreter
from cross_structure import CrossStructure, MultiCrossStructure
from jcross_condition_evaluator import EmotionTriggerEvaluator
from jcross_resource_extractor import ResourceAllocationExtractor


class EmotionDNASystem:
    """
    感情DNAシステム（Cross構造版）

    .jcrossファイルから感情DNAを読み込み、
    Cross構造として実行する
    """

    def __init__(self, jcross_file: Optional[str] = None):
        """
        Initialize

        Args:
            jcross_file: emotion_dna_cross.jcrossのパス（Noneの場合はデフォルト）
        """
        if jcross_file is None:
            # デフォルトパスを使用
            jcross_file = Path(__file__).parent.parent / "vision" / "emotion_dna_cross.jcross"

        # .jcrossファイルを読み込み
        print(f"📖 感情DNAを読み込み: {jcross_file}")
        interpreter = JCrossInterpreter()
        jcross_data = interpreter.load_file(str(jcross_file))

        # MultiCrossStructureに変換
        self.multi_cross = MultiCrossStructure(jcross_data)

        # Layer 0: ホメオスタシス閾値
        self.homeostasis_crosses = {
            "体温": self.multi_cross.get("体温Cross"),
            "エネルギー": self.multi_cross.get("エネルギーCross"),
            "痛み": self.multi_cross.get("痛みCross"),
            "酸素": self.multi_cross.get("酸素Cross")
        }

        # Layer 1: 神経伝達物質
        self.neurotransmitter_crosses = {
            "ドーパミン": self.multi_cross.get("ドーパミンCross"),
            "ノルアドレナリン": self.multi_cross.get("ノルアドレナリンCross"),
            "セロトニン": self.multi_cross.get("セロトニンCross")
        }

        # Layer 2: 感情
        self.emotion_crosses = {
            "恐怖": self.multi_cross.get("恐怖Cross"),
            "怒り": self.multi_cross.get("怒りCross"),
            "好奇心": self.multi_cross.get("好奇心Cross"),
            "悲しみ": self.multi_cross.get("悲しみCross"),
            "喜び": self.multi_cross.get("喜びCross"),
            "安心": self.multi_cross.get("安心Cross")
        }

        # Stage 1: 発火条件評価器
        self.trigger_evaluator = EmotionTriggerEvaluator()

        # Stage 2: リソース配分抽出器
        self.resource_extractor = ResourceAllocationExtractor()

        # 現在の神経伝達物質レベル
        self.current_neurotransmitters = {
            "dopamine": 0.0,
            "noradrenaline": 0.0,
            "serotonin": 0.5
        }

        # 現在の感情
        self.current_emotion = None
        self.current_emotion_name = "なし"
        self.current_emotion_intensity = 0.0

        print(f"✅ 感情DNA読み込み完了")
        print(f"  Layer 0 (ホメオスタシス): {len(self.homeostasis_crosses)}個")
        print(f"  Layer 1 (神経伝達物質): {len(self.neurotransmitter_crosses)}個")
        print(f"  Layer 2 (感情): {len(self.emotion_crosses)}個")

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
            prediction_error: 予測誤差 (0.0-1.0)
            similar_experiences_count: 類似経験数
            sync_degree: 同調度 (0.0-1.0)
            discomfort_decreased: 不快感が減少したか
            new_pattern_found: 新パターン発見
        """
        # ドーパミン放出条件をチェック
        dopamine_cross = self.neurotransmitter_crosses["ドーパミン"]
        if dopamine_cross:
            # 予測成功
            if prediction_error < 0.05:
                self.current_neurotransmitters["dopamine"] += 1.0

            # 同調成功
            if sync_degree > 0.8:
                self.current_neurotransmitters["dopamine"] += 0.8

            # 不快解消
            if discomfort_decreased:
                self.current_neurotransmitters["dopamine"] += 1.0

            # 新発見
            if new_pattern_found:
                self.current_neurotransmitters["dopamine"] += 0.6

            # 上限
            self.current_neurotransmitters["dopamine"] = min(1.0, self.current_neurotransmitters["dopamine"])

        # ノルアドレナリン放出条件をチェック
        noradrenaline_cross = self.neurotransmitter_crosses["ノルアドレナリン"]
        if noradrenaline_cross:
            # 予測失敗
            if prediction_error > 0.5:
                self.current_neurotransmitters["noradrenaline"] += 1.0

            # 未知
            if similar_experiences_count == 0:
                self.current_neurotransmitters["noradrenaline"] += 0.8

            # 上限
            self.current_neurotransmitters["noradrenaline"] = min(1.0, self.current_neurotransmitters["noradrenaline"])

        # セロトニン放出条件をチェック
        serotonin_cross = self.neurotransmitter_crosses["セロトニン"]
        if serotonin_cross:
            # 反復同調
            if similar_experiences_count >= 5 and prediction_error < 0.1:
                self.current_neurotransmitters["serotonin"] += 0.6
                self.current_neurotransmitters["serotonin"] = min(1.0, self.current_neurotransmitters["serotonin"])

    def decay_neurotransmitters(self, decay_rate: float = 0.1):
        """
        神経伝達物質の減衰

        Args:
            decay_rate: 減衰率
        """
        self.current_neurotransmitters["dopamine"] *= (1.0 - decay_rate)
        self.current_neurotransmitters["noradrenaline"] *= (1.0 - decay_rate)

        # セロトニンは0.5に戻る傾向
        if self.current_neurotransmitters["serotonin"] > 0.5:
            self.current_neurotransmitters["serotonin"] -= decay_rate * 0.5
        else:
            self.current_neurotransmitters["serotonin"] += decay_rate * 0.5

    def determine_emotion(
        self,
        physiological_state: Dict[str, Any],
        cognitive_state: Dict[str, Any]
    ) -> Optional[CrossStructure]:
        """
        感情を判定（Cross構造として）

        Stage 1: .jcrossのFRONT軸の発火条件を実際に評価

        Args:
            physiological_state: 生理状態
            cognitive_state: 認知状態

        Returns:
            発火した感情のCross構造、またはNone
        """
        candidates = []

        # 各感情CrossのFRONT軸発火条件を実際に評価
        for emotion_name, emotion_cross in self.emotion_crosses.items():
            if emotion_cross is None:
                continue

            # Stage 1: .jcrossに記述された発火条件を評価
            should_trigger = self.trigger_evaluator.evaluate_emotion_trigger(
                emotion_cross,
                physiological_state,
                cognitive_state
            )

            if should_trigger:
                # 発火強度を計算
                intensity = self.trigger_evaluator.calculate_trigger_intensity(
                    emotion_cross,
                    physiological_state,
                    cognitive_state
                )

                # UP軸から優先度を取得
                priority = self._get_emotion_priority(emotion_cross)

                candidates.append({
                    "name": emotion_name,
                    "cross": emotion_cross,
                    "priority": priority,
                    "intensity": intensity
                })

        # 優先度が最も高い感情を選択
        if not candidates:
            self.current_emotion = None
            self.current_emotion_name = "なし"
            self.current_emotion_intensity = 0.0
            return None

        # 最高優先度
        dominant = max(candidates, key=lambda x: x["priority"])

        self.current_emotion = dominant["cross"]
        self.current_emotion_name = dominant["name"]
        self.current_emotion_intensity = dominant["intensity"]

        return self.current_emotion

    def _get_emotion_priority(self, emotion_cross: CrossStructure) -> int:
        """
        感情CrossのUP軸から優先度を取得

        Args:
            emotion_cross: 感情Cross構造

        Returns:
            優先度（整数）
        """
        if "UP" not in emotion_cross.metadata:
            return 5  # デフォルト優先度

        up_data = emotion_cross.metadata["UP"]

        for point in up_data:
            if isinstance(point, dict) and "優先度" in point:
                return int(point["優先度"])

        return 5  # デフォルト

    def get_resource_allocation(self) -> Dict[str, float]:
        """
        現在の感情のリソース配分を取得

        Stage 2: .jcrossのRIGHT軸から自動抽出

        Returns:
            リソース配分辞書
        """
        if self.current_emotion is None:
            return {
                "explore": 0.5,
                "learn": 0.5,
                "predict": 0.5,
                "memory": 0.5,
                "flee": 0.0,
                "attack": 0.0,
                "rest": 0.5
            }

        # Stage 2: RIGHT軸から自動抽出
        return self.resource_extractor.extract_from_cross(self.current_emotion)

    def get_sync_mode(self) -> str:
        """
        現在の感情の同調モードを取得

        Stage 2: .jcrossのLEFT軸から自動抽出

        Returns:
            同調モード文字列
        """
        if self.current_emotion is None:
            return "normal_mode"

        return self.resource_extractor.extract_sync_mode(self.current_emotion)

    def get_emotion_color(self) -> str:
        """
        現在の感情の色を取得

        Returns:
            色の名前
        """
        color_map = {
            "恐怖": "赤（警告）",
            "怒り": "暗赤（憤怒）",
            "好奇心": "オレンジ（好奇）",
            "悲しみ": "青（沈静）",
            "喜び": "黄（明るい）",
            "安心": "緑（安定）",
            "なし": "無色"
        }
        return color_map.get(self.current_emotion_name, "不明")

    def get_status(self) -> Dict[str, Any]:
        """
        現在の状態を取得

        Returns:
            状態辞書
        """
        return {
            "current_emotion": {
                "name": self.current_emotion_name,
                "intensity": self.current_emotion_intensity,
                "color": self.get_emotion_color(),
                "resource_allocation": self.get_resource_allocation()
            },
            "neurotransmitters": self.current_neurotransmitters.copy()
        }


def main():
    """テスト用メイン関数"""
    print("=" * 80)
    print("感情DNAシステムテスト（Cross構造版）")
    print("=" * 80)
    print()

    # 感情DNAシステムを初期化
    emotion_dna = EmotionDNASystem()

    print()
    print("=" * 80)
    print("シナリオ1: 未知のものに遭遇（好奇心）")
    print("=" * 80)

    # イベント処理
    emotion_dna.process_event(
        prediction_error=0.6,
        similar_experiences_count=0,
        sync_degree=0.2,
        new_pattern_found=True
    )

    # 感情判定
    emotion = emotion_dna.determine_emotion(
        physiological_state={
            "pain": 0.0,
            "energy": 100.0,
            "critical_deviation": False,
            "all_deviation": 0.0
        },
        cognitive_state={
            "total_discomfort": 0.7,
            "novelty_discomfort": 0.8,
            "resolution_failures": 0
        }
    )

    status = emotion_dna.get_status()
    print(f"感情: {status['current_emotion']['name']}")
    print(f"強度: {status['current_emotion']['intensity']:.2f}")
    print(f"色: {status['current_emotion']['color']}")
    print(f"リソース配分: {status['current_emotion']['resource_allocation']}")
    print(f"神経伝達物質: {status['neurotransmitters']}")

    print()
    print("=" * 80)
    print("シナリオ2: 予測成功（喜び）")
    print("=" * 80)

    # イベント処理
    emotion_dna.process_event(
        prediction_error=0.02,
        similar_experiences_count=10,
        sync_degree=0.9,
        discomfort_decreased=True
    )

    # 感情判定
    emotion = emotion_dna.determine_emotion(
        physiological_state={
            "pain": 0.0,
            "energy": 100.0,
            "critical_deviation": False,
            "all_deviation": 0.0
        },
        cognitive_state={
            "total_discomfort": 0.1,
            "novelty_discomfort": 0.0,
            "resolution_failures": 0
        }
    )

    status = emotion_dna.get_status()
    print(f"感情: {status['current_emotion']['name']}")
    print(f"強度: {status['current_emotion']['intensity']:.2f}")
    print(f"色: {status['current_emotion']['color']}")
    print(f"リソース配分: {status['current_emotion']['resource_allocation']}")
    print(f"神経伝達物質: {status['neurotransmitters']}")


if __name__ == "__main__":
    main()
