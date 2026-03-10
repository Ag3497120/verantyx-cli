#!/usr/bin/env python3
"""
Emotion Inference Engine
感情推測エンジン

過去の経験から未来を推測し、感情を形成する。
ラベルなし。システム自身が推測する。
"""

from pathlib import Path
from typing import Dict, Any, Optional
import sys

try:
    import cv2
    import numpy as np
    from PIL import Image
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from verantyx_cli.vision.experience_memory import ExperienceMemory


class EmotionInference:
    """感情推測エンジン"""

    def __init__(self, memory: ExperienceMemory):
        """
        Initialize emotion inference

        Args:
            memory: 経験記憶
        """
        self.memory = memory
        self.current_emotion = None
        self.emotion_history = []

    def infer(self, current_cross: Dict[str, Any]) -> Dict[str, Any]:
        """
        現在のCross構造から感情を推測

        Args:
            current_cross: 現在のCross構造

        Returns:
            感情（6軸＋メタデータ）
        """
        # 1. 最も類似した過去の瞬間を探す
        similar_moments = self.memory.find_similar_moments(
            current_cross,
            top_k=5,
            min_similarity=0.5
        )

        if not similar_moments:
            # 未知の経験 → 「新鮮さ」
            emotion = self._create_novelty_emotion()
            print("💭 感情: 新鮮さ（未知の経験）")
        else:
            # 類似した経験あり → 「期待」を形成
            emotion = self._create_expectation_emotion(similar_moments, current_cross)

        # 2. 感情を記録
        self.current_emotion = emotion
        self.emotion_history.append(emotion)

        return emotion

    def _create_novelty_emotion(self) -> Dict[str, Any]:
        """新鮮さの感情（未知）"""
        return {
            "type": "novelty",
            "description": "新鮮さ",

            # 6軸マッピング
            "FRONT": 0.8,  # 高い期待（未知への好奇心）
            "BACK": 0.1,   # 記憶が薄い
            "UP": 0.7,     # 高揚（警戒）
            "DOWN": 0.3,   # 落ち着きが低い
            "RIGHT": 0.5,  # 中立
            "LEFT": 0.5,   # 中立

            "confidence": 0.3,  # 低い確信度
            "expected_next": None,
            "similar_moments": []
        }

    def _create_expectation_emotion(
        self,
        similar_moments: list,
        current_cross: Dict[str, Any]
    ) -> Dict[str, Any]:
        """期待の感情（推測）"""
        best_match = similar_moments[0]
        similarity = best_match["similarity"]
        timestamp = best_match["timestamp"]

        # 次の瞬間を推測
        next_moment = self.memory.get_next_moment(timestamp)

        if next_moment:
            expected_next = next_moment["cross_structure"]
            description = "期待"
        else:
            expected_next = None
            description = "懐かしさ"

        # 感情を6軸にマッピング
        axes = self._map_to_axes(similarity, expected_next)

        emotion = {
            "type": "expectation" if expected_next else "nostalgia",
            "description": description,

            # 6軸
            **axes,

            "confidence": similarity,
            "memory_timestamp": timestamp,
            "similarity": similarity,
            "expected_next": expected_next,
            "similar_moments": similar_moments
        }

        # デバッグ出力
        print(f"💭 感情: {description}")
        print(f"   記憶: タイムスタンプ {timestamp}")
        print(f"   類似度: {similarity:.1%}")
        print(f"   確信度: {similarity:.1%}")

        return emotion

    def _map_to_axes(
        self,
        confidence: float,
        expected_next: Optional[Dict]
    ) -> Dict[str, float]:
        """感情を6軸にマッピング"""

        # 確信度が高い = 安心 = DOWN軸
        # 確信度が低い = 不安 = UP軸
        down_val = confidence
        up_val = 1.0 - confidence

        # 期待がある = FRONT軸
        # 期待がない = BACK軸
        if expected_next:
            front_val = confidence
            back_val = 0.3
        else:
            front_val = 0.3
            back_val = confidence

        return {
            "FRONT": front_val,
            "BACK": back_val,
            "UP": up_val,
            "DOWN": down_val,
            "RIGHT": 0.5,  # 現時点では中立
            "LEFT": 0.5    # 現時点では中立
        }

    def validate_prediction(self, actual_next: Dict[str, Any]) -> Dict[str, Any]:
        """
        予測を検証（実際の次の瞬間と比較）

        Args:
            actual_next: 実際の次のCross構造

        Returns:
            報酬（満足/驚き）
        """
        if not self.current_emotion:
            return {"type": "neutral"}

        expected = self.current_emotion.get("expected_next")
        if not expected:
            return {"type": "neutral"}

        # ズレを計測
        surprise = self._calculate_surprise(expected, actual_next)

        print(f"🎯 予測の検証:")
        print(f"   ズレ: {surprise:.1%}")

        if surprise < 0.2:
            # 予測が当たった → 満足
            reward = {
                "type": "satisfaction",
                "description": "満足",
                "UP": 0.6,      # 喜び
                "DOWN": 0.8,    # 安心
                "FRONT": 0.9,   # 期待の強化
                "BACK": 0.3,
                "RIGHT": 0.5,
                "LEFT": 0.5,
                "surprise": surprise
            }
            print("   → ✅ 満足（予測が当たった）")
        else:
            # 予測が外れた → 驚き
            reward = {
                "type": "surprise",
                "description": "驚き",
                "UP": 0.9,      # 強い反応
                "DOWN": 0.2,    # 不安
                "FRONT": 0.3,   # 期待の修正
                "BACK": 0.7,    # 記憶の見直し
                "RIGHT": 0.5,
                "LEFT": 0.5,
                "surprise": surprise
            }
            print("   → ⚠️  驚き（予測が外れた）")

        # 報酬を記録
        self.emotion_history.append(reward)

        return reward

    def _calculate_surprise(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any]
    ) -> float:
        """驚きの度合いを計算（予測と現実のズレ）"""
        similarity = self.memory._calculate_similarity(expected, actual)
        surprise = 1.0 - similarity
        return surprise

    def express_emotion(self, emotion: Dict[str, Any]) -> str:
        """感情を言語化"""
        if not emotion:
            return "無感情"

        emotion_type = emotion.get("type", "unknown")
        description = emotion.get("description", "")
        confidence = emotion.get("confidence", 0)

        # 6軸の値から詳細な表現
        up = emotion.get("UP", 0)
        down = emotion.get("DOWN", 0)
        front = emotion.get("FRONT", 0)
        back = emotion.get("BACK", 0)

        # パターンマッチング
        if emotion_type == "novelty":
            return f"新鮮さ（好奇心: {front:.0%}, 警戒: {up:.0%}）"
        elif emotion_type == "expectation":
            return f"期待（確信: {down:.0%}, 予測: {front:.0%}）"
        elif emotion_type == "satisfaction":
            return f"満足（喜び: {up:.0%}, 安心: {down:.0%}）"
        elif emotion_type == "surprise":
            return f"驚き（反応: {up:.0%}, 不安: {1-down:.0%}）"
        elif emotion_type == "nostalgia":
            return f"懐かしさ（記憶: {back:.0%}, 確信: {confidence:.0%}）"
        else:
            return f"{description}（確信: {confidence:.0%}）"

    def get_emotion_summary(self) -> Dict[str, Any]:
        """感情のサマリーを取得"""
        if not self.emotion_history:
            return {"total": 0}

        # 感情タイプの集計
        type_counts = {}
        for emotion in self.emotion_history:
            emotion_type = emotion.get("type", "unknown")
            type_counts[emotion_type] = type_counts.get(emotion_type, 0) + 1

        # 平均確信度
        confidences = [
            e.get("confidence", 0)
            for e in self.emotion_history
            if "confidence" in e
        ]
        avg_confidence = np.mean(confidences) if confidences else 0

        return {
            "total": len(self.emotion_history),
            "type_counts": type_counts,
            "avg_confidence": avg_confidence,
            "latest": self.current_emotion
        }


class EmotionVisualizer:
    """感情の可視化"""

    def visualize(self, frame, emotion: Dict[str, Any], inference: EmotionInference):
        """
        感情をカメラ映像にオーバーレイ

        Args:
            frame: 映像フレーム
            emotion: 感情
            inference: 推測エンジン
        """
        if not emotion:
            return

        if not CV2_AVAILABLE:
            return

        height, width = frame.shape[:2]

        # 背景矩形（半透明効果）
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # 感情の言語化
        emotion_text = inference.express_emotion(emotion)

        # 感情タイプアイコン
        emotion_type = emotion.get("type", "unknown")
        icon = self._get_emotion_icon(emotion_type)

        # 感情表示
        cv2.putText(
            frame, f"{icon} {emotion_text}", (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
            (255, 255, 255), 2
        )

        # 確信度表示
        confidence = emotion.get("confidence", 0)
        if confidence > 0:
            cv2.putText(
                frame, f"確信度: {confidence:.0%}", (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1
            )

        # 6軸の値を表示
        y_pos = 100
        for axis_name in ["FRONT", "UP", "DOWN"]:
            value = emotion.get(axis_name, 0)
            bar_length = int(value * 200)

            # 軸名
            axis_label = self._get_axis_label(axis_name)
            cv2.putText(
                frame, axis_label, (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1
            )

            # バー背景
            cv2.rectangle(
                frame,
                (120, y_pos - 15),
                (320, y_pos - 5),
                (50, 50, 50), -1
            )

            # バー
            color = self._get_axis_color(axis_name, value)
            cv2.rectangle(
                frame,
                (120, y_pos - 15),
                (120 + bar_length, y_pos - 5),
                color, -1
            )

            # 値
            cv2.putText(
                frame, f"{value:.0%}", (330, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1
            )

            y_pos += 25

        # 記憶タイムスタンプ表示（期待/懐かしさの場合）
        if "memory_timestamp" in emotion:
            timestamp = emotion["memory_timestamp"]
            similarity = emotion.get("similarity", 0)
            cv2.putText(
                frame, f"記憶: #{timestamp} (類似: {similarity:.0%})", (10, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (150, 150, 150), 1
            )

    def _get_emotion_icon(self, emotion_type: str) -> str:
        """感情タイプのアイコンを取得"""
        icons = {
            "novelty": "✨",
            "expectation": "🎯",
            "nostalgia": "💫",
            "satisfaction": "😊",
            "surprise": "😮",
            "neutral": "😐"
        }
        return icons.get(emotion_type, "💭")

    def _get_axis_label(self, axis_name: str) -> str:
        """軸のラベルを取得"""
        labels = {
            "FRONT": "期待:",
            "BACK": "記憶:",
            "UP": "高揚:",
            "DOWN": "安心:",
            "RIGHT": "接近:",
            "LEFT": "回避:"
        }
        return labels.get(axis_name, f"{axis_name}:")

    def _get_axis_color(self, axis_name: str, value: float):
        """軸の色を取得"""
        if axis_name == "FRONT":
            # 緑系（期待）
            return (0, int(255 * value), 0)
        elif axis_name == "UP":
            # 赤系（高揚・警戒）
            return (0, 0, int(255 * value))
        elif axis_name == "DOWN":
            # 青系（安心）
            return (int(255 * value), int(200 * value), 0)
        elif axis_name == "BACK":
            # 紫系（記憶）
            return (int(200 * value), 0, int(255 * value))
        elif axis_name == "RIGHT":
            # 黄色系（接近）
            return (0, int(255 * value), int(255 * value))
        elif axis_name == "LEFT":
            # シアン系（回避）
            return (int(255 * value), int(255 * value), 0)
        else:
            return (200, 200, 200)
