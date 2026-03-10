#!/usr/bin/env python3
"""
Global Cross Registry
グローバルCross構造レジストリ

Phase 4: 全ノード同調
- すべてのCross構造を一元管理
- 感情発火時に全Cross構造に伝播
- リソース配分の実際の適用
"""

from typing import Dict, Any, List, Optional, Set
from cross_structure import CrossStructure
import threading


class GlobalCrossRegistry:
    """
    グローバルCross構造レジストリ

    システム内のすべてのCross構造を管理し、
    感情による全ノード同調を実現する
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """シングルトンパターン"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize"""
        if self._initialized:
            return

        self.crosses: Dict[str, CrossStructure] = {}
        self.cross_groups: Dict[str, Set[str]] = {
            "perception": set(),      # 知覚系Cross
            "memory": set(),          # 記憶系Cross
            "emotion": set(),         # 感情系Cross
            "motor": set(),           # 運動系Cross
            "prediction": set()       # 予測系Cross
        }

        # 現在のリソース配分
        self.current_resource_allocation: Dict[str, float] = {
            "explore": 0.5,
            "learn": 0.5,
            "predict": 0.5,
            "memory": 0.5,
            "flee": 0.0,
            "attack": 0.0,
            "rest": 0.5
        }

        # 現在の同調モード
        self.current_sync_mode = "normal_mode"

        # 感情による強制割り込みフラグ
        self.emotion_interrupt_active = False
        self.current_emotion = None

        self._initialized = True

    def register(
        self,
        name: str,
        cross: CrossStructure,
        group: Optional[str] = None
    ):
        """
        Cross構造を登録

        Args:
            name: Cross構造の名前
            cross: CrossStructure
            group: グループ名（perception/memory/emotion/motor/prediction）
        """
        self.crosses[name] = cross

        if group and group in self.cross_groups:
            self.cross_groups[group].add(name)

    def unregister(self, name: str):
        """
        Cross構造を登録解除

        Args:
            name: Cross構造の名前
        """
        if name in self.crosses:
            del self.crosses[name]

            # グループからも削除
            for group in self.cross_groups.values():
                group.discard(name)

    def get(self, name: str) -> Optional[CrossStructure]:
        """
        Cross構造を取得

        Args:
            name: Cross構造の名前

        Returns:
            CrossStructure、またはNone
        """
        return self.crosses.get(name)

    def apply_global_resource_allocation(self, allocation: Dict[str, float]):
        """
        全Cross構造にリソース配分を適用

        感情が発火したときに呼ばれる

        Args:
            allocation: リソース配分辞書
        """
        print(f"🎨 全ノード同調: リソース配分を適用")
        print(f"   新しい配分: {allocation}")

        self.current_resource_allocation = allocation.copy()

        # すべてのCross構造に適用
        for name, cross in self.crosses.items():
            cross.apply_resource_allocation(allocation)

        print(f"   適用完了: {len(self.crosses)}個のCross構造")

    def apply_global_sync_mode(self, mode: str):
        """
        全Cross構造に同調モードを適用

        Args:
            mode: 同調モード（flee_mode/attack_mode/explore_learn_mode等）
        """
        print(f"🎨 全ノード同調: モードを変更")
        print(f"   新しいモード: {mode}")

        self.current_sync_mode = mode

        # 各モードに応じた処理
        if mode == "flee_mode":
            # 逃走モード: 学習・探索を停止
            self._disable_learning_and_exploration()
        elif mode == "attack_mode":
            # 攻撃モード: 学習を抑制
            self._suppress_learning()
        elif mode == "explore_learn_mode":
            # 探索・学習モード: 全開
            self._enable_learning_and_exploration()
        elif mode == "energy_save_mode":
            # 省エネモード: 探索停止
            self._disable_exploration()

        print(f"   モード変更完了")

    def emotion_interrupt(
        self,
        emotion_name: str,
        resource_allocation: Dict[str, float],
        sync_mode: str
    ):
        """
        感情による強制割り込み

        感情が発火したときに、全Cross構造に強制的に伝播

        Args:
            emotion_name: 感情名
            resource_allocation: リソース配分
            sync_mode: 同調モード
        """
        print()
        print("=" * 80)
        print(f"⚡ 感情割り込み発火: {emotion_name}")
        print("=" * 80)

        self.emotion_interrupt_active = True
        self.current_emotion = emotion_name

        # リソース配分を適用
        self.apply_global_resource_allocation(resource_allocation)

        # 同調モードを適用
        self.apply_global_sync_mode(sync_mode)

        print("=" * 80)
        print()

    def clear_emotion_interrupt(self):
        """
        感情割り込みをクリア

        感情が収まったときに呼ばれる
        """
        print(f"🔄 感情割り込み解除: {self.current_emotion}")

        self.emotion_interrupt_active = False
        self.current_emotion = None

        # デフォルトのリソース配分に戻す
        default_allocation = {
            "explore": 0.5,
            "learn": 0.5,
            "predict": 0.5,
            "memory": 0.5,
            "flee": 0.0,
            "attack": 0.0,
            "rest": 0.5
        }

        self.apply_global_resource_allocation(default_allocation)
        self.apply_global_sync_mode("normal_mode")

    def get_active_crosses_by_resource(self, resource: str, threshold: float = 0.5) -> List[str]:
        """
        特定のリソースが活性化しているCross構造を取得

        Args:
            resource: リソース名
            threshold: 閾値

        Returns:
            Cross構造名のリスト
        """
        active = []

        resource_value = self.current_resource_allocation.get(resource, 0.0)

        if resource_value >= threshold:
            # このリソースが活性化している
            # 対応するグループのCross構造を返す
            if resource == "explore":
                active.extend(self.cross_groups["perception"])
            elif resource == "learn":
                active.extend(self.cross_groups["memory"])
            elif resource == "predict":
                active.extend(self.cross_groups["prediction"])
            elif resource == "flee" or resource == "attack":
                active.extend(self.cross_groups["motor"])

        return active

    def _disable_learning_and_exploration(self):
        """学習と探索を無効化（逃走モード）"""
        # 記憶系と知覚系のCrossを抑制
        for name in self.cross_groups["memory"]:
            if name in self.crosses:
                # 簡易実装: RIGHT軸の学習リソースを0にする
                self.crosses[name].right[1] = 0.0  # learn

        for name in self.cross_groups["perception"]:
            if name in self.crosses:
                self.crosses[name].right[0] = 0.0  # explore

    def _suppress_learning(self):
        """学習を抑制（攻撃モード）"""
        for name in self.cross_groups["memory"]:
            if name in self.crosses:
                self.crosses[name].right[1] = 0.2  # learn = 0.2

    def _enable_learning_and_exploration(self):
        """学習と探索を全開（探索・学習モード）"""
        for name in self.cross_groups["memory"]:
            if name in self.crosses:
                self.crosses[name].right[1] = 1.0  # learn

        for name in self.cross_groups["perception"]:
            if name in self.crosses:
                self.crosses[name].right[0] = 1.0  # explore

    def _disable_exploration(self):
        """探索を無効化（省エネモード）"""
        for name in self.cross_groups["perception"]:
            if name in self.crosses:
                self.crosses[name].right[0] = 0.1  # explore

    def get_status(self) -> Dict[str, Any]:
        """
        現在の状態を取得

        Returns:
            状態辞書
        """
        return {
            "total_crosses": len(self.crosses),
            "groups": {
                name: len(crosses)
                for name, crosses in self.cross_groups.items()
            },
            "current_resource_allocation": self.current_resource_allocation.copy(),
            "current_sync_mode": self.current_sync_mode,
            "emotion_interrupt_active": self.emotion_interrupt_active,
            "current_emotion": self.current_emotion
        }

    def __repr__(self) -> str:
        return f"<GlobalCrossRegistry: {len(self.crosses)} crosses, mode={self.current_sync_mode}>"


# グローバルインスタンスを取得する関数
def get_global_registry() -> GlobalCrossRegistry:
    """
    グローバルレジストリのシングルトンインスタンスを取得

    Returns:
        GlobalCrossRegistry
    """
    return GlobalCrossRegistry()


def main():
    """テスト用メイン関数"""
    from jcross_interpreter import JCrossInterpreter
    from cross_structure import MultiCrossStructure

    print("=" * 80)
    print("グローバルCrossレジストリテスト")
    print("=" * 80)
    print()

    # レジストリを取得
    registry = get_global_registry()

    # .jcrossファイルを読み込み
    interpreter = JCrossInterpreter()
    data = interpreter.load_file("../vision/emotion_dna_cross.jcross")

    # Cross構造を登録
    multi_cross = MultiCrossStructure(data)

    for name, cross in multi_cross.crosses.items():
        # グループを決定
        if "感情" in name or "Cross" in name and any(e in name for e in ["恐怖", "怒り", "喜び", "悲しみ", "安心", "好奇心"]):
            group = "emotion"
        elif "記憶" in name:
            group = "memory"
        else:
            group = "perception"

        registry.register(name, cross, group)

    print(f"登録完了: {len(registry.crosses)}個のCross構造")
    print()

    # 状態表示
    status = registry.get_status()
    print("初期状態:")
    print(f"  リソース配分: {status['current_resource_allocation']}")
    print(f"  同調モード: {status['current_sync_mode']}")
    print()

    # 感情割り込み（恐怖）
    registry.emotion_interrupt(
        emotion_name="恐怖",
        resource_allocation={
            "flee": 1.0,
            "learn": 0.0,
            "explore": 0.0,
            "predict": 0.1,
            "memory": 1.0
        },
        sync_mode="flee_mode"
    )

    # 状態表示
    status = registry.get_status()
    print("恐怖発火後:")
    print(f"  リソース配分: {status['current_resource_allocation']}")
    print(f"  同調モード: {status['current_sync_mode']}")
    print(f"  割り込み中: {status['emotion_interrupt_active']}")
    print()

    # 感情割り込み解除
    registry.clear_emotion_interrupt()

    # 状態表示
    status = registry.get_status()
    print("割り込み解除後:")
    print(f"  リソース配分: {status['current_resource_allocation']}")
    print(f"  同調モード: {status['current_sync_mode']}")


if __name__ == "__main__":
    main()
