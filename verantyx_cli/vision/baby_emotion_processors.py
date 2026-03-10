#!/usr/bin/env python3
"""
Baby Emotion Processors
赤ちゃん感情システム用プロセッサ

JCross言語で書かれた baby_emotion.jcross を実行するための
プロセッサ群。
"""

from typing import Dict, Any, List, Optional
import hashlib
import json


class BabyEmotionProcessor:
    """赤ちゃん感情プロセッサ（基底クラス）"""

    def __init__(self):
        """Initialize processor"""
        self.state = {
            # 感覚パラメータ
            "sensory": {
                "discomfort": {"value": 0.3, "threshold": 0.7, "axis": "UP", "color": None},
                "hunger": {"value": 0.4, "threshold": 0.7, "axis": "DOWN", "color": None},
                "pain": {"value": 0.2, "threshold": 0.8, "axis": "BACK", "color": None},
                "tiredness": {"value": 0.5, "threshold": 0.7, "axis": "DOWN", "color": None}
            },

            # 記憶（多層Cross構造）
            "memory": {
                "timeline": [],  # 層のリスト
                "max_layers": 1000
            },

            # 発達レベル
            "development": {
                "current_level": 0,
                "observation_count": 0,
                "thresholds": {
                    0: 0,
                    1: 10,
                    2: 50,
                    3: 100,
                    4: 200
                }
            },

            # Level 1: パターン記憶
            "patterns": {},  # pattern_id -> count

            # Level 2: 因果関係
            "causal_links": [],

            # Level 3: 言語
            "labels": {},  # pattern_id -> label

            # Level 4: 概念
            "concepts": {}  # label -> emotional_color
        }

    def process(self, command: str, params: Dict[str, Any]) -> Any:
        """
        JCrossコマンドを処理

        Args:
            command: コマンド名
            params: パラメータ

        Returns:
            処理結果
        """
        method_name = f"process_{command}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(params)
        else:
            return {"error": f"Unknown command: {command}"}


class ObservationProcessor(BabyEmotionProcessor):
    """観測プロセッサ"""

    def process_observe(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        観測処理（Level 0）

        Args:
            params: {"cross_structure": Cross構造}

        Returns:
            観測Cross
        """
        cross_structure = params.get("cross_structure", {})

        # 感覚パラメータの現在値を読み取る
        sensory_values = {
            name: data["value"]
            for name, data in self.state["sensory"].items()
        }

        # Cross構造に感覚を統合
        observation_cross = {
            "external": cross_structure,  # 外界
            "internal": sensory_values,    # 内界（感覚）
            "timestamp": self.state["development"]["observation_count"],
            "color": None  # まだ色はない
        }

        # 記憶に追加（新しい層として）
        self.state["memory"]["timeline"].append(observation_cross)

        # 観測回数をインクリメント
        self.state["development"]["observation_count"] += 1

        # レベルアップチェック
        self._check_level_up()

        return observation_cross

    def _check_level_up(self):
        """レベルアップ判定"""
        count = self.state["development"]["observation_count"]
        current_level = self.state["development"]["current_level"]
        thresholds = self.state["development"]["thresholds"]

        for level, threshold in thresholds.items():
            if count >= threshold and current_level < level:
                self.state["development"]["current_level"] = level
                print(f"🎉 Level {level} 到達!")
                self._print_level_description(level)

    def _print_level_description(self, level: int):
        """レベルの説明"""
        descriptions = {
            0: "記憶機能のみ（色なし、意味なし）",
            1: "パターン蓄積開始（繰り返しを検出）",
            2: "因果関係の発見（これをすると→こうなる）",
            3: "言語獲得準備完了（パターンにラベルを付けられる）",
            4: "概念形成可能（感情に色がつく）"
        }
        print(f"   {descriptions.get(level, '未知のレベル')}")


class PatternProcessor(BabyEmotionProcessor):
    """パターン検出プロセッサ（Level 1）"""

    def process_detect_pattern(self, params: Dict[str, Any]) -> Optional[str]:
        """
        パターン検出

        Args:
            params: {"observation_cross": 観測Cross}

        Returns:
            パターンID
        """
        if self.state["development"]["current_level"] < 1:
            return None

        observation = params.get("observation_cross", {})

        # Cross構造を粗く量子化
        simplified = self._simplify_cross(observation.get("external", {}))

        # ハッシュ化してパターンIDを生成
        pattern_id = self._hash_pattern(simplified)

        # 出現回数を記録
        if pattern_id not in self.state["patterns"]:
            self.state["patterns"][pattern_id] = 0
        self.state["patterns"][pattern_id] += 1

        return pattern_id

    def _simplify_cross(self, cross_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Cross構造を粗く量子化（0.2刻み）"""
        simplified = {}

        if "axes" in cross_structure:
            for axis_name, axis_data in cross_structure["axes"].items():
                mean_val = axis_data.get("mean", 0.5)
                # 0.2刻みで量子化
                quantized = round(mean_val * 5) / 5
                simplified[axis_name] = quantized

        return simplified

    def _hash_pattern(self, pattern: Dict[str, Any]) -> str:
        """パターンをハッシュ化"""
        pattern_str = json.dumps(pattern, sort_keys=True)
        return hashlib.sha256(pattern_str.encode()).hexdigest()[:16]


class CausalProcessor(BabyEmotionProcessor):
    """因果関係プロセッサ（Level 2）"""

    def process_discover_causality(self, params: Dict[str, Any]) -> bool:
        """
        因果関係を発見

        Args:
            params: {
                "pattern_id": パターンID,
                "action": 行動,
                "result": 結果
            }

        Returns:
            成功したかどうか
        """
        if self.state["development"]["current_level"] < 2:
            return False

        pattern_id = params.get("pattern_id")
        action = params.get("action")
        result = params.get("result")

        # 既存の因果関係を検索
        for link in self.state["causal_links"]:
            if (link["pattern"] == pattern_id and
                link["action"] == action and
                link["result"] == result):
                # 強度を増加
                link["strength"] += 1
                return True

        # 新しい因果関係を追加
        self.state["causal_links"].append({
            "pattern": pattern_id,
            "action": action,
            "result": result,
            "strength": 1,
            "color": None  # まだ色はない
        })

        return True


class ActionProcessor(BabyEmotionProcessor):
    """行動プロセッサ"""

    def __init__(self):
        """Initialize action processor"""
        super().__init__()
        self.causal_processor = None  # 後で設定

    def process_cry(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        泣く行動

        Args:
            params: {}

        Returns:
            行動Cross
        """
        # トリガー条件チェック
        triggered = False
        for name, data in self.state["sensory"].items():
            if data["value"] > data["threshold"]:
                triggered = True
                break

        if not triggered:
            return {"action": "cry", "triggered": False}

        # 泣く前の感覚値を記録
        before_sensory = {
            name: data["value"]
            for name, data in self.state["sensory"].items()
        }

        # 泣くというCross構造を生成
        cry_cross = {
            "action": "cry",
            "axis": "UP",  # 上昇（警告信号）
            "intensity": 0.9,
            "color": None,
            "triggered": True,
            "before_sensory": before_sensory
        }

        return cry_cross

    def process_check_causality_after_cry(self, params: Dict[str, Any]) -> bool:
        """
        泣いた後の因果関係チェック

        Args:
            params: {
                "pattern_id": パターンID,
                "before_sensory": 泣く前の感覚値
            }

        Returns:
            因果関係が発見されたか
        """
        if self.state["development"]["current_level"] < 2:
            return False

        before = params.get("before_sensory", {})
        pattern_id = params.get("pattern_id")

        # 感覚値の変化をチェック
        for name, before_value in before.items():
            after_value = self.state["sensory"][name]["value"]
            delta = after_value - before_value

            if abs(delta) > 0.2:  # 大きな変化
                if delta < 0:
                    result = f"{name}_decreased"
                else:
                    result = f"{name}_increased"

                # 因果関係を記録（CausalProcessorを使う）
                if self.causal_processor:
                    self.causal_processor.process_discover_causality({
                        "pattern_id": pattern_id,
                        "action": "cry",
                        "result": result
                    })

                return True

        return False


class LanguageProcessor(BabyEmotionProcessor):
    """言語プロセッサ（Level 3）"""

    def process_learn_label(self, params: Dict[str, Any]) -> bool:
        """
        ラベルを学習

        Args:
            params: {
                "pattern_id": パターンID,
                "label": ラベル
            }

        Returns:
            成功したかどうか
        """
        if self.state["development"]["current_level"] < 3:
            print(f"⚠️  まだLevel 3に到達していません（現在Level {self.state['development']['current_level']}）")
            return False

        pattern_id = params.get("pattern_id")
        label = params.get("label")

        # パターンIDにラベルを付ける
        self.state["labels"][pattern_id] = label

        # 記憶に逆伝播（そのパターンを持つ全ての記憶にラベルを付ける）
        for observation in self.state["memory"]["timeline"]:
            if observation.get("pattern_id") == pattern_id:
                observation["label"] = label
                observation["color"] = None  # まだ色はない

        print(f"📚 ラベル学習: {pattern_id[:8]}... → '{label}'")
        return True


class ConceptProcessor(BabyEmotionProcessor):
    """概念プロセッサ（Level 4）"""

    def process_form_concept(self, params: Dict[str, Any]) -> bool:
        """
        概念を形成（感情に色をつける）

        Args:
            params: {
                "label": ラベル,
                "emotional_color": 感情の色
            }

        Returns:
            成功したかどうか
        """
        if self.state["development"]["current_level"] < 4:
            print(f"⚠️  まだLevel 4に到達していません（現在Level {self.state['development']['current_level']}）")
            return False

        label = params.get("label")
        emotional_color = params.get("emotional_color")

        # ラベルに感情の色を付ける
        self.state["concepts"][label] = emotional_color

        # 記憶に色を付ける
        for observation in self.state["memory"]["timeline"]:
            if observation.get("label") == label:
                observation["color"] = emotional_color

        # 因果関係にも色を付ける
        for link in self.state["causal_links"]:
            pattern_id = link["pattern"]
            if self.state["labels"].get(pattern_id) == label:
                link["color"] = emotional_color

        print(f"🎨 概念形成: '{label}' に感情の色がつきました")
        print(f"   色: {emotional_color}")

        return True


class SensoryProcessor(BabyEmotionProcessor):
    """感覚プロセッサ"""

    def process_update_sensory(self, params: Dict[str, Any]) -> bool:
        """
        感覚パラメータを更新

        Args:
            params: {
                "name": パラメータ名,
                "delta": 変化量
            }

        Returns:
            成功したかどうか
        """
        name = params.get("name")
        delta = params.get("delta", 0)

        if name in self.state["sensory"]:
            current = self.state["sensory"][name]["value"]
            new_value = max(0.0, min(1.0, current + delta))
            self.state["sensory"][name]["value"] = new_value
            return True

        return False

    def process_get_triggered_sensations(self, params: Dict[str, Any]) -> List[str]:
        """
        トリガーされた感覚を取得

        Returns:
            トリガーされた感覚のリスト
        """
        triggered = []
        for name, data in self.state["sensory"].items():
            if data["value"] > data["threshold"]:
                triggered.append(name)
        return triggered


# ===================================================================
# 統合プロセッサ
# ===================================================================

class BabyEmotionSystemProcessor:
    """赤ちゃん感情システム統合プロセッサ"""

    def __init__(self):
        """Initialize system processor"""
        # 全てのプロセッサを統合
        self.observation = ObservationProcessor()
        self.pattern = PatternProcessor()
        self.causal = CausalProcessor()
        self.action = ActionProcessor()
        self.language = LanguageProcessor()
        self.concept = ConceptProcessor()
        self.sensory = SensoryProcessor()

        # ActionProcessorにCausalProcessorを渡す
        self.action.causal_processor = self.causal

        # 状態を共有
        self._share_state()

    def _share_state(self):
        """全プロセッサで状態を共有"""
        state = self.observation.state
        self.pattern.state = state
        self.causal.state = state
        self.action.state = state
        self.language.state = state
        self.concept.state = state
        self.sensory.state = state

    def get_state(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        return self.observation.state

    def print_status(self):
        """ステータスを表示"""
        state = self.get_state()

        print()
        print("=" * 70)
        print("赤ちゃん感情システム - ステータス")
        print("=" * 70)
        print(f"現在のレベル: Level {state['development']['current_level']}")
        print(f"観測回数: {state['development']['observation_count']}")
        print()
        print(f"パターン数: {len(state['patterns'])}")
        print(f"因果関係数: {len(state['causal_links'])}")
        print(f"ラベル数: {len(state['labels'])}")
        print(f"概念数: {len(state['concepts'])}")
        print()
        print("感覚パラメータ:")
        for name, data in state['sensory'].items():
            triggered = "⚠️ " if data['value'] > data['threshold'] else "   "
            print(f"  {triggered}{name}: {data['value']:.2f} (閾値: {data['threshold']})")
        print("=" * 70)
        print()
