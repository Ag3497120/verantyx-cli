#!/usr/bin/env python3
"""
Kofdai型全同調エンジン - 実運用版

全パターンが同時に共鳴し、最大共鳴が自然に選ばれる
データは削除されず、6次元空間内で再配置される
"""

import time
import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class ResonancePattern:
    """共鳴パターン"""
    name: str
    keywords: List[str]
    threshold: float
    action: str

    # Cross空間座標
    front_back: float = 0.5  # FRONT/BACK: 品質（成功率）
    up_down: float = 0.5     # UP/DOWN: 使用頻度
    left_right: float = 1.0  # LEFT/RIGHT: 新しさ
    axis_4: float = 0.5      # 実体関連度
    axis_5: float = 0.5      # 意図一致度
    axis_6: float = 0.5      # 時間的新しさ

    # 統計情報
    usage_count: int = 0
    success_count: int = 0
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def quality(self) -> float:
        """品質スコア（成功率）"""
        if self.usage_count == 0:
            return 0.5
        return self.success_count / self.usage_count

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'name': self.name,
            'keywords': self.keywords,
            'threshold': self.threshold,
            'action': self.action,
            'position': {
                'front_back': self.front_back,
                'up_down': self.up_down,
                'left_right': self.left_right,
                'axis_4': self.axis_4,
                'axis_5': self.axis_5,
                'axis_6': self.axis_6
            },
            'stats': {
                'usage_count': self.usage_count,
                'success_count': self.success_count,
                'quality': self.quality,
                'created_at': self.created_at
            }
        }

    @staticmethod
    def from_dict(data: Dict) -> 'ResonancePattern':
        """辞書から復元"""
        pattern = ResonancePattern(
            name=data['name'],
            keywords=data['keywords'],
            threshold=data['threshold'],
            action=data['action']
        )

        if 'position' in data:
            pos = data['position']
            pattern.front_back = pos.get('front_back', 0.5)
            pattern.up_down = pos.get('up_down', 0.5)
            pattern.left_right = pos.get('left_right', 1.0)
            pattern.axis_4 = pos.get('axis_4', 0.5)
            pattern.axis_5 = pos.get('axis_5', 0.5)
            pattern.axis_6 = pos.get('axis_6', 0.5)

        if 'stats' in data:
            stats = data['stats']
            pattern.usage_count = stats.get('usage_count', 0)
            pattern.success_count = stats.get('success_count', 0)
            pattern.created_at = stats.get('created_at', time.time())

        return pattern


@dataclass
class ResonanceResult:
    """共鳴結果"""
    pattern_name: str
    score: float
    action: str
    threshold: float
    confidence: str  # "high", "medium", "low"


class KofdaiResonanceEngine:
    """
    Kofdai型全同調エンジン

    原則:
    1. 全パターンが同時に共鳴
    2. 最大共鳴が自然に選ばれる
    3. データは削除されず、空間内で再配置される
    4. 成功したパターンがFRONT-UPへ移動
    """

    def __init__(self, patterns_file: Optional[Path] = None):
        """
        Args:
            patterns_file: パターン保存ファイル（.json）
        """
        self.patterns_file = patterns_file or Path.home() / '.verantyx' / 'resonance_patterns.json'
        self.patterns: List[ResonancePattern] = []

        # デフォルトパターンを初期化
        self._init_default_patterns()

        # 既存パターンがあれば読み込み
        self._load_patterns()

    def _init_default_patterns(self):
        """デフォルトパターンを初期化"""
        default_patterns = [
            ResonancePattern(
                name="definition_query",
                keywords=["とは", "って何", "の意味", "について"],
                threshold=0.6,
                action="semantic_search"
            ),
            ResonancePattern(
                name="explanation_request",
                keywords=["教えて", "説明して", "を説明", "詳しく"],
                threshold=0.65,
                action="semantic_search"
            ),
            ResonancePattern(
                name="greeting",
                keywords=["こんにちは", "おはよう", "こんばんは", "やあ", "hello", "hi"],
                threshold=0.7,
                action="greeting_response"
            ),
            ResonancePattern(
                name="gratitude",
                keywords=["ありがと", "感謝", "助かった", "thanks"],
                threshold=0.7,
                action="gratitude_response"
            ),
            ResonancePattern(
                name="pronoun_reference",
                keywords=["それ", "これ", "あれ"],
                threshold=0.8,
                action="resolve_pronoun"
            )
        ]

        self.patterns = default_patterns

    def _load_patterns(self):
        """保存されたパターンを読み込み"""
        if not self.patterns_file.exists():
            return

        try:
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            loaded_patterns = []
            for p_data in data.get('patterns', []):
                loaded_patterns.append(ResonancePattern.from_dict(p_data))

            # デフォルトパターンと統合（保存版を優先）
            loaded_names = {p.name for p in loaded_patterns}
            for default_p in self.patterns:
                if default_p.name not in loaded_names:
                    loaded_patterns.append(default_p)

            self.patterns = loaded_patterns

        except Exception as e:
            print(f"⚠️  Failed to load patterns: {e}")

    def save_patterns(self):
        """パターンを保存"""
        self.patterns_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'patterns': [p.to_dict() for p in self.patterns],
            'last_updated': time.time()
        }

        with open(self.patterns_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def calculate_resonance(self, text: str, pattern: ResonancePattern) -> float:
        """
        テキストとパターンの共鳴度を計算

        Args:
            text: 入力テキスト（エネルギー波）
            pattern: 共鳴パターン

        Returns:
            共鳴度 (0.0-1.0)
        """
        text_lower = text.lower()
        match_count = 0

        for keyword in pattern.keywords:
            if keyword.lower() in text_lower:
                match_count += 1

        if len(pattern.keywords) == 0:
            return 0.0

        score = match_count / len(pattern.keywords)
        return score

    def trigger_all_resonances(self, text: str) -> List[ResonanceResult]:
        """
        全パターンで並列共鳴を計算

        Kofdai原則: 全パターンが同時に共鳴し、最大共鳴が自然に選ばれる

        Args:
            text: 入力テキスト（エネルギー波）

        Returns:
            全共鳴結果のリスト
        """
        resonances = []

        for pattern in self.patterns:
            score = self.calculate_resonance(text, pattern)

            # Logic Resolution: 閾値に基づいて信頼度を判定
            if score >= pattern.threshold:
                confidence = "high"
            elif score >= 0.5:
                confidence = "medium"
            else:
                confidence = "low"

            resonances.append(ResonanceResult(
                pattern_name=pattern.name,
                score=score,
                action=pattern.action,
                threshold=pattern.threshold,
                confidence=confidence
            ))

        return resonances

    def find_best_resonance(self, resonances: List[ResonanceResult]) -> ResonanceResult:
        """
        最大共鳴を自然に選択

        Args:
            resonances: 全共鳴結果

        Returns:
            最大共鳴パターン
        """
        if not resonances:
            return ResonanceResult(
                pattern_name="none",
                score=0.0,
                action="learn_new_pattern",
                threshold=0.5,
                confidence="low"
            )

        # 最大スコアを持つパターンを選択
        best = max(resonances, key=lambda r: r.score)
        return best

    def update_pattern_position(self, pattern_name: str, success: bool = False):
        """
        パターンをCross空間内で再配置

        Kofdai原則: データは削除されず、空間内で再配置される
        成功したパターンはFRONT-UPへ移動

        Args:
            pattern_name: パターン名
            success: 実行が成功したか
        """
        pattern = self._get_pattern(pattern_name)
        if not pattern:
            return

        # 使用統計を更新
        pattern.usage_count += 1
        if success:
            pattern.success_count += 1

        # 6次元空間での位置を再計算

        # FRONT/BACK: 品質（成功率）
        pattern.front_back = pattern.quality

        # UP/DOWN: 使用頻度
        pattern.up_down = min(pattern.usage_count / 100.0, 1.0)

        # LEFT/RIGHT: 新しさ
        age_seconds = time.time() - pattern.created_at
        age_days = age_seconds / 86400.0
        pattern.left_right = max(1.0 - (age_days / 365.0), 0.0)

        # パターンを保存
        self.save_patterns()

    def _get_pattern(self, pattern_name: str) -> Optional[ResonancePattern]:
        """パターンを名前で取得"""
        for pattern in self.patterns:
            if pattern.name == pattern_name:
                return pattern
        return None

    def process_input_wave(self, text: str, execute: bool = False) -> Dict[str, Any]:
        """
        入力をエネルギー波として処理

        Kofdai型全同調の完全な実行フロー:
        1. 全パターンが同時に共鳴
        2. 最大共鳴が自然に選ばれる
        3. Logic Resolution（閾値判定）
        4. アクション決定
        5. Cross空間で再配置

        Args:
            text: 入力テキスト（エネルギー波）
            execute: 実際にアクションを実行するか

        Returns:
            処理結果
        """
        # 1. 全パターンで並列共鳴
        resonances = self.trigger_all_resonances(text)

        # 2. 最大共鳴を選択
        best = self.find_best_resonance(resonances)

        # 3. Logic Resolution
        decision = {
            'input': text,
            'best_pattern': best.pattern_name,
            'score': best.score,
            'threshold': best.threshold,
            'confidence': best.confidence,
            'action': best.action,
            'all_resonances': [
                {
                    'pattern': r.pattern_name,
                    'score': r.score,
                    'confidence': r.confidence
                }
                for r in sorted(resonances, key=lambda x: x.score, reverse=True)
            ]
        }

        # 4. アクション実行（オプション）
        if execute and best.confidence in ["high", "medium"]:
            success = self._execute_action(best.action, text)
            decision['executed'] = True
            decision['success'] = success

            # 5. Cross空間で再配置
            self.update_pattern_position(best.pattern_name, success)
        else:
            decision['executed'] = False

        return decision

    def _execute_action(self, action: str, text: str) -> bool:
        """
        アクションを実行

        Args:
            action: アクション名
            text: 入力テキスト

        Returns:
            成功したか
        """
        # アクションは外部システムと統合
        # ここでは実行フラグのみ返す
        return True

    def get_space_visualization(self) -> str:
        """Cross空間の視覚化"""
        lines = []
        lines.append("=" * 60)
        lines.append("📊 6次元Cross空間 - パターン配置")
        lines.append("=" * 60)
        lines.append("")

        # パターンを品質順にソート
        sorted_patterns = sorted(
            self.patterns,
            key=lambda p: (p.front_back, p.up_down),
            reverse=True
        )

        for pattern in sorted_patterns:
            lines.append(f"Pattern: {pattern.name}")
            lines.append(f"  Position: FRONT={pattern.front_back:.2f} "
                        f"UP={pattern.up_down:.2f} "
                        f"RIGHT={pattern.left_right:.2f}")
            lines.append(f"  Stats: Usage={pattern.usage_count} "
                        f"Success={pattern.success_count} "
                        f"Quality={pattern.quality:.2f}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


if __name__ == "__main__":
    # テスト
    engine = KofdaiResonanceEngine()

    print("🌊 Kofdai Resonance Engine - Test")
    print("=" * 60)
    print("")

    # テスト入力
    test_inputs = [
        "openaiとは何ですか？",
        "それについて教えて",
        "ありがとうございます",
        "こんにちは"
    ]

    for text in test_inputs:
        print(f"Input: {text}")
        result = engine.process_input_wave(text, execute=True)
        print(f"  → Pattern: {result['best_pattern']}")
        print(f"  → Score: {result['score']:.1%}")
        print(f"  → Confidence: {result['confidence']}")
        print(f"  → Action: {result['action']}")
        print("")

    # 空間状態表示
    print(engine.get_space_visualization())
