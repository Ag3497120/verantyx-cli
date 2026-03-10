#!/usr/bin/env python3
"""
JCross Resource Extractor
JCrossリソース配分抽出器

Stage 2: emotion_dna_cross.jcrossのRIGHT軸からリソース配分を自動抽出
"""

from typing import Dict, Any, Optional
from cross_structure import CrossStructure


class ResourceAllocationExtractor:
    """
    Cross構造のRIGHT軸からリソース配分を抽出
    """

    def __init__(self):
        """Initialize"""
        # リソース名の標準化マッピング
        self.resource_name_mapping = {
            # 日本語 → 英語キー
            "探索": "explore",
            "学習": "learn",
            "予測": "predict",
            "記憶": "memory",
            "逃走": "flee",
            "攻撃": "attack",
            "休息": "rest",
            "逃走準備": "flee",
            "攻撃準備": "attack",
            # 英語もそのまま
            "explore": "explore",
            "learn": "learn",
            "predict": "predict",
            "memory": "memory",
            "flee": "flee",
            "attack": "attack",
            "rest": "rest"
        }

    def extract_from_cross(self, cross: CrossStructure) -> Dict[str, float]:
        """
        Cross構造のRIGHT軸からリソース配分を抽出

        Args:
            cross: Cross構造

        Returns:
            リソース配分辞書 {"explore": 1.0, "learn": 0.9, ...}
        """
        allocation = {}

        if "RIGHT" not in cross.metadata:
            return allocation

        right_data = cross.metadata["RIGHT"]

        for point in right_data:
            if not isinstance(point, dict):
                continue

            # リソース名を探す
            resource_name = None
            resource_value = None

            for key in ["リソース", "resource", "Resource"]:
                if key in point:
                    resource_name = point[key]
                    break

            if resource_name is None:
                continue

            # 配分値を探す
            for key in ["配分", "allocation", "value", "値"]:
                if key in point:
                    resource_value = float(point[key])
                    break

            if resource_value is None:
                continue

            # 標準化されたキーに変換
            normalized_key = self.resource_name_mapping.get(resource_name)
            if normalized_key:
                allocation[normalized_key] = resource_value
            else:
                # マッピングにない場合はそのまま使用
                allocation[resource_name] = resource_value

        return allocation

    def extract_sync_mode(self, cross: CrossStructure) -> str:
        """
        Cross構造のLEFT軸から同調モードを抽出

        Args:
            cross: Cross構造

        Returns:
            同調モード文字列
        """
        if "LEFT" not in cross.metadata:
            return "normal_mode"

        left_data = cross.metadata["LEFT"]

        for point in left_data:
            if not isinstance(point, dict):
                continue

            # 同調モードを探す
            for key in ["同調モード", "sync_mode", "mode"]:
                if key in point:
                    mode_str = point[key]

                    # 標準化
                    mode_mapping = {
                        "逃走モード": "flee_mode",
                        "攻撃モード": "attack_mode",
                        "能動探索モード": "explore_learn_mode",
                        "省エネモード": "energy_save_mode",
                        "通常モード": "normal_mode",
                        "flee_mode": "flee_mode",
                        "attack_mode": "attack_mode",
                        "explore_learn_mode": "explore_learn_mode",
                        "energy_save_mode": "energy_save_mode",
                        "normal_mode": "normal_mode"
                    }

                    return mode_mapping.get(mode_str, "normal_mode")

        return "normal_mode"

    def extract_priority(self, cross: CrossStructure) -> int:
        """
        Cross構造のUP軸から優先度を抽出

        Args:
            cross: Cross構造

        Returns:
            優先度（整数）
        """
        if "UP" not in cross.metadata:
            return 5  # デフォルト

        up_data = cross.metadata["UP"]

        for point in up_data:
            if not isinstance(point, dict):
                continue

            for key in ["優先度", "priority"]:
                if key in point:
                    return int(point[key])

        return 5

    def extract_full_emotion_config(self, emotion_cross: CrossStructure) -> Dict[str, Any]:
        """
        感情Cross構造から全ての設定を抽出

        Args:
            emotion_cross: 感情Cross構造

        Returns:
            設定辞書
        """
        return {
            "resource_allocation": self.extract_from_cross(emotion_cross),
            "sync_mode": self.extract_sync_mode(emotion_cross),
            "priority": self.extract_priority(emotion_cross),
            "metadata": emotion_cross.metadata
        }


def main():
    """テスト用メイン関数"""
    print("=" * 80)
    print("JCrossリソース配分抽出器テスト")
    print("=" * 80)
    print()

    from jcross_interpreter import JCrossInterpreter
    from cross_structure import MultiCrossStructure
    from pathlib import Path

    # emotion_dna_cross.jcrossを読み込み
    jcross_file = Path(__file__).parent.parent / "vision" / "emotion_dna_cross.jcross"
    interpreter = JCrossInterpreter()
    data = interpreter.load_file(str(jcross_file))

    multi_cross = MultiCrossStructure(data)

    extractor = ResourceAllocationExtractor()

    # 恐怖Crossのリソース配分を抽出
    print("【恐怖Cross】")
    fear_cross = multi_cross.get("恐怖Cross")
    if fear_cross:
        allocation = extractor.extract_from_cross(fear_cross)
        sync_mode = extractor.extract_sync_mode(fear_cross)
        priority = extractor.extract_priority(fear_cross)

        print(f"  リソース配分: {allocation}")
        print(f"  同調モード: {sync_mode}")
        print(f"  優先度: {priority}")
    print()

    # 好奇心Crossのリソース配分を抽出
    print("【好奇心Cross】")
    curiosity_cross = multi_cross.get("好奇心Cross")
    if curiosity_cross:
        allocation = extractor.extract_from_cross(curiosity_cross)
        sync_mode = extractor.extract_sync_mode(curiosity_cross)
        priority = extractor.extract_priority(curiosity_cross)

        print(f"  リソース配分: {allocation}")
        print(f"  同調モード: {sync_mode}")
        print(f"  優先度: {priority}")
    print()

    # 喜びCrossのリソース配分を抽出
    print("【喜びCross】")
    joy_cross = multi_cross.get("喜びCross")
    if joy_cross:
        config = extractor.extract_full_emotion_config(joy_cross)
        print(f"  リソース配分: {config['resource_allocation']}")
        print(f"  同調モード: {config['sync_mode']}")
        print(f"  優先度: {config['priority']}")
    print()

    print("✅ Stage 2完了: .jcrossのRIGHT軸からリソース配分を自動抽出")


if __name__ == "__main__":
    main()
