#!/usr/bin/env python3
"""
Developmental Emotion System
発達段階的感情システム

赤ちゃんのように、段階を踏んで感情を獲得する。

Level 0: 記憶 + 感覚（色なし）
Level 1: パターン蓄積
Level 2: 因果関係の発見
Level 3: 言語獲得（ラベル）
Level 4: 概念形成（感情の色）
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import hashlib

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class SensoryParameter:
    """感覚パラメータ（生得的）"""

    def __init__(self, name: str, initial_value: float = 0.5):
        """
        Initialize sensory parameter

        Args:
            name: パラメータ名（例: "discomfort", "hunger"）
            initial_value: 初期値（0.0 - 1.0）
        """
        self.name = name
        self.value = initial_value
        self.threshold = 0.7  # この値を超えたら「シグナル」を発する

    def update(self, delta: float):
        """値を更新"""
        self.value = max(0.0, min(1.0, self.value + delta))

    def is_triggered(self) -> bool:
        """閾値を超えたか"""
        return self.value > self.threshold

    def reset(self):
        """リセット"""
        self.value = 0.5


class Level0Memory:
    """Level 0: 記憶機能（生得的、色なし）"""

    def __init__(self, memory_path: Optional[Path] = None):
        """
        Initialize Level 0 memory

        Args:
            memory_path: 記憶ファイルのパス
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required")

        if memory_path is None:
            memory_path = Path.home() / ".verantyx" / "developmental_memory.json"

        self.memory_path = memory_path
        self.timeline = []  # 時系列の経験（色なし）

        # 既存の記憶を読み込み
        if self.memory_path.exists():
            self.load()

    def record(self, observation: Dict[str, Any]):
        """
        観測を記録（色なし、ラベルなし）

        Args:
            observation: 観測データ（Cross構造 + 感覚パラメータ）
        """
        timestamp = len(self.timeline)

        record = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "observation": observation,
            # 色なし、意味なし、ただの記録
        }

        self.timeline.append(record)

        # 自動保存（100記録ごと）
        if len(self.timeline) % 100 == 0:
            self.save()

    def recall(self, index: int) -> Optional[Dict[str, Any]]:
        """記憶を呼び出す"""
        if 0 <= index < len(self.timeline):
            return self.timeline[index]
        return None

    def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """直近のn個の記憶を取得"""
        return self.timeline[-n:] if len(self.timeline) >= n else self.timeline

    def save(self):
        """記憶を保存"""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "level": 0,
            "saved_at": datetime.now().isoformat(),
            "record_count": len(self.timeline),
            "timeline": self.timeline
        }

        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self):
        """記憶を読み込み"""
        if not self.memory_path.exists():
            return

        with open(self.memory_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.timeline = data.get("timeline", [])


class Level1PatternAccumulation:
    """Level 1: パターン蓄積（繰り返しを検出）"""

    def __init__(self, memory: Level0Memory):
        """
        Initialize Level 1 pattern accumulation

        Args:
            memory: Level 0記憶
        """
        self.memory = memory
        self.patterns = {}  # パターンID -> 出現回数

    def detect_pattern(self, observation: Dict[str, Any]) -> Optional[str]:
        """
        パターンを検出（まだ意味はない）

        Args:
            observation: 観測データ

        Returns:
            パターンID（ハッシュ）
        """
        # 観測を単純化してハッシュ化
        pattern_str = self._simplify_observation(observation)
        pattern_id = hashlib.sha256(pattern_str.encode()).hexdigest()[:16]

        # パターンの出現回数を記録
        if pattern_id not in self.patterns:
            self.patterns[pattern_id] = 0
        self.patterns[pattern_id] += 1

        return pattern_id

    def _simplify_observation(self, observation: Dict[str, Any]) -> str:
        """観測を単純化（粗い量子化）"""
        # Cross構造を粗く量子化（0.2刻み）
        simplified = {}

        cross = observation.get("cross_structure", {})
        if "axes" in cross:
            for axis_name, axis_data in cross["axes"].items():
                mean_val = axis_data.get("mean", 0.5)
                # 0.2刻みで量子化
                quantized = round(mean_val * 5) / 5
                simplified[axis_name] = quantized

        # 感覚パラメータも粗く量子化
        sensory = observation.get("sensory_params", {})
        for param_name, param_value in sensory.items():
            quantized = round(param_value * 5) / 5
            simplified[f"sensory_{param_name}"] = quantized

        return json.dumps(simplified, sort_keys=True)

    def get_pattern_frequency(self, pattern_id: str) -> int:
        """パターンの出現頻度を取得"""
        return self.patterns.get(pattern_id, 0)

    def is_frequent_pattern(self, pattern_id: str, threshold: int = 3) -> bool:
        """頻出パターンか判定"""
        return self.get_pattern_frequency(pattern_id) >= threshold


class Level2CausalDiscovery:
    """Level 2: 因果関係の発見（繰り返しから法則を見つける）"""

    def __init__(self, memory: Level0Memory):
        """
        Initialize Level 2 causal discovery

        Args:
            memory: Level 0記憶
        """
        self.memory = memory
        self.causal_links = []  # 因果関係のリスト

    def discover_causality(self, pattern_id: str, action: str, result: str):
        """
        因果関係を発見

        Args:
            pattern_id: パターンID
            action: 行動（例: "cry", "move"）
            result: 結果（例: "discomfort_decreased"）
        """
        # 既存の因果関係を検索
        for link in self.causal_links:
            if (link["pattern"] == pattern_id and
                link["action"] == action and
                link["result"] == result):
                # 既存の因果関係の強度を増加
                link["strength"] += 1
                return

        # 新しい因果関係を追加
        self.causal_links.append({
            "pattern": pattern_id,
            "action": action,
            "result": result,
            "strength": 1,  # 初回は強度1
            "discovered_at": datetime.now().isoformat()
        })

    def get_causal_links(self, pattern_id: str) -> List[Dict[str, Any]]:
        """特定パターンの因果関係を取得"""
        return [
            link for link in self.causal_links
            if link["pattern"] == pattern_id
        ]

    def get_strongest_action(self, pattern_id: str) -> Optional[str]:
        """最も強い因果関係の行動を取得"""
        links = self.get_causal_links(pattern_id)
        if not links:
            return None

        strongest = max(links, key=lambda x: x["strength"])
        return strongest["action"]


class Level3LanguageAcquisition:
    """Level 3: 言語獲得（パターンにラベルを付ける）"""

    def __init__(self):
        """Initialize Level 3 language acquisition"""
        self.labels = {}  # パターンID -> ラベル

    def assign_label(self, pattern_id: str, label: str):
        """
        パターンにラベルを付ける（人間が教える）

        Args:
            pattern_id: パターンID
            label: ラベル（例: "discomfort", "hunger"）
        """
        self.labels[pattern_id] = label

    def get_label(self, pattern_id: str) -> Optional[str]:
        """パターンのラベルを取得"""
        return self.labels.get(pattern_id)

    def has_label(self, pattern_id: str) -> bool:
        """ラベルが付いているか"""
        return pattern_id in self.labels


class Level4ConceptFormation:
    """Level 4: 概念形成（感情に色がつく）"""

    def __init__(self, language: Level3LanguageAcquisition, causality: Level2CausalDiscovery):
        """
        Initialize Level 4 concept formation

        Args:
            language: Level 3言語獲得
            causality: Level 2因果関係
        """
        self.language = language
        self.causality = causality
        self.concepts = {}  # ラベル -> 概念（感情の色）

    def form_concept(self, label: str, emotional_valence: Dict[str, float]):
        """
        概念を形成（感情に色をつける）

        Args:
            label: ラベル（例: "discomfort"）
            emotional_valence: 感情の色（例: {"unpleasant": 0.8, "arousal": 0.6}）
        """
        self.concepts[label] = {
            "label": label,
            "emotional_valence": emotional_valence,
            "formed_at": datetime.now().isoformat()
        }

    def get_concept(self, label: str) -> Optional[Dict[str, Any]]:
        """概念を取得"""
        return self.concepts.get(label)

    def has_concept(self, label: str) -> bool:
        """概念が形成されているか"""
        return label in self.concepts


class DevelopmentalEmotionSystem:
    """発達段階的感情システム"""

    def __init__(self, memory_path: Optional[Path] = None):
        """
        Initialize developmental emotion system

        Args:
            memory_path: 記憶ファイルのパス
        """
        # Level 0: 記憶（生得的）
        self.memory = Level0Memory(memory_path=memory_path)

        # Level 1: パターン蓄積
        self.pattern_accumulation = Level1PatternAccumulation(self.memory)

        # Level 2: 因果関係の発見
        self.causal_discovery = Level2CausalDiscovery(self.memory)

        # Level 3: 言語獲得
        self.language_acquisition = Level3LanguageAcquisition()

        # Level 4: 概念形成
        self.concept_formation = Level4ConceptFormation(
            self.language_acquisition,
            self.causal_discovery
        )

        # 感覚パラメータ（生得的）
        self.sensory_params = {
            "discomfort": SensoryParameter("discomfort", initial_value=0.3),
            "hunger": SensoryParameter("hunger", initial_value=0.4),
            "pain": SensoryParameter("pain", initial_value=0.2),
            "tiredness": SensoryParameter("tiredness", initial_value=0.5)
        }

        # 現在のレベル（0から開始）
        self.current_level = 0

        # 発達の閾値
        self.level_thresholds = {
            0: 0,      # Level 0: 最初から
            1: 10,     # Level 1: 10回の観測後
            2: 50,     # Level 2: 50回の観測後（パターンが蓄積）
            3: 100,    # Level 3: 100回の観測後（言語獲得の準備）
            4: 200     # Level 4: 200回の観測後（概念形成）
        }

    def observe(self, cross_structure: Dict[str, Any], action: Optional[str] = None):
        """
        観測して記録

        Args:
            cross_structure: Cross構造
            action: 実行した行動（オプション）
        """
        # 感覚パラメータを読み取る
        sensory_state = {
            name: param.value
            for name, param in self.sensory_params.items()
        }

        # 観測データを構築
        observation = {
            "cross_structure": cross_structure,
            "sensory_params": sensory_state,
            "action": action
        }

        # Level 0: 記憶（常に実行）
        self.memory.record(observation)

        # Level 1: パターン検出
        if self.current_level >= 1:
            pattern_id = self.pattern_accumulation.detect_pattern(observation)
            observation["pattern_id"] = pattern_id

        # Level 2: 因果関係の発見
        if self.current_level >= 2 and action:
            self._check_causality(observation, action)

        # レベルアップの判定
        self._check_level_up()

        return observation

    def _check_causality(self, observation: Dict[str, Any], action: str):
        """因果関係をチェック"""
        pattern_id = observation.get("pattern_id")
        if not pattern_id:
            return

        # 感覚パラメータの変化をチェック
        prev_observations = self.memory.get_recent(2)
        if len(prev_observations) < 2:
            return

        prev_sensory = prev_observations[-2]["observation"]["sensory_params"]
        curr_sensory = observation["sensory_params"]

        # 変化を検出
        for param_name, prev_value in prev_sensory.items():
            curr_value = curr_sensory[param_name]
            delta = curr_value - prev_value

            if abs(delta) > 0.2:  # 大きな変化
                if delta < 0:
                    result = f"{param_name}_decreased"
                else:
                    result = f"{param_name}_increased"

                # 因果関係を記録
                self.causal_discovery.discover_causality(pattern_id, action, result)

    def _check_level_up(self):
        """レベルアップの判定"""
        observation_count = len(self.memory.timeline)

        for level, threshold in self.level_thresholds.items():
            if observation_count >= threshold and self.current_level < level:
                self.current_level = level
                print(f"🎉 Level Up! → Level {level}")
                self._print_level_description(level)

    def _print_level_description(self, level: int):
        """レベルの説明を表示"""
        descriptions = {
            0: "記憶機能のみ（色なし、意味なし）",
            1: "パターン蓄積開始（繰り返しを検出）",
            2: "因果関係の発見（「これをすると→こうなる」）",
            3: "言語獲得準備（パターンにラベルを付けられる）",
            4: "概念形成（感情に色がつく）"
        }
        print(f"   {descriptions.get(level, '未知のレベル')}")

    def update_sensory_param(self, param_name: str, delta: float):
        """感覚パラメータを更新"""
        if param_name in self.sensory_params:
            self.sensory_params[param_name].update(delta)

    def get_triggered_sensations(self) -> List[str]:
        """トリガーされた感覚を取得"""
        return [
            name for name, param in self.sensory_params.items()
            if param.is_triggered()
        ]

    def teach_label(self, pattern_id: str, label: str):
        """
        パターンにラベルを教える（Level 3）

        Args:
            pattern_id: パターンID
            label: ラベル（例: "discomfort"）
        """
        if self.current_level >= 3:
            self.language_acquisition.assign_label(pattern_id, label)
            print(f"📚 ラベル学習: {pattern_id[:8]}... → '{label}'")
        else:
            print(f"⚠️  まだLevel 3に到達していません（現在Level {self.current_level}）")

    def teach_concept(self, label: str, emotional_valence: Dict[str, float]):
        """
        概念を教える（Level 4）

        Args:
            label: ラベル
            emotional_valence: 感情の色
        """
        if self.current_level >= 4:
            self.concept_formation.form_concept(label, emotional_valence)
            print(f"🎨 概念形成: '{label}' に感情の色がつきました")
        else:
            print(f"⚠️  まだLevel 4に到達していません（現在Level {self.current_level}）")

    def get_status(self) -> Dict[str, Any]:
        """現在のステータスを取得"""
        return {
            "current_level": self.current_level,
            "observation_count": len(self.memory.timeline),
            "pattern_count": len(self.pattern_accumulation.patterns),
            "causal_link_count": len(self.causal_discovery.causal_links),
            "label_count": len(self.language_acquisition.labels),
            "concept_count": len(self.concept_formation.concepts),
            "sensory_state": {
                name: {
                    "value": param.value,
                    "triggered": param.is_triggered()
                }
                for name, param in self.sensory_params.items()
            }
        }

    def print_status(self):
        """ステータスを表示"""
        status = self.get_status()

        print()
        print("=" * 70)
        print("発達段階的感情システム - ステータス")
        print("=" * 70)
        print(f"現在のレベル: Level {status['current_level']}")
        print(f"観測回数: {status['observation_count']}")
        print()
        print(f"パターン数: {status['pattern_count']}")
        print(f"因果関係数: {status['causal_link_count']}")
        print(f"ラベル数: {status['label_count']}")
        print(f"概念数: {status['concept_count']}")
        print()
        print("感覚パラメータ:")
        for name, state in status['sensory_state'].items():
            triggered = "⚠️ " if state['triggered'] else "   "
            print(f"  {triggered}{name}: {state['value']:.2f}")
        print("=" * 70)
        print()
