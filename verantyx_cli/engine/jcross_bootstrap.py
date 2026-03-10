#!/usr/bin/env python3
"""
JCross Bootstrap
JCrossブートストラップ

JCrossコードを実行するための最小限のPythonブリッジ。
Pythonは表示とI/Oのみ。ロジックは全てJCross。
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class JCrossRuntime:
    """
    JCrossランタイム

    JCrossコードを実行する最小限の環境。
    全てのロジックはJCrossで実装。
    """

    def __init__(self):
        """Initialize runtime"""
        self.state = {}
        self.functions = {}
        self.stack = []

    def execute_file(self, filepath: Path) -> Dict[str, Any]:
        """
        JCrossファイルを実行

        Args:
            filepath: .jcrossファイルのパス

        Returns:
            実行結果
        """
        # TODO: JCrossパーサー実装
        # 現時点では、JCrossコードを直接評価する簡易版

        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()

        # JCrossコードをPythonで解釈（ブートストラップ版）
        return self._interpret_jcross(code)

    def _interpret_jcross(self, code: str) -> Dict[str, Any]:
        """
        JCrossコードを解釈（簡易版）

        NOTE: 本来はJCrossパーサー+VMで実行すべきだが、
        ブートストラップのため、最小限の実装。
        """
        # JCrossコードから状態オブジェクトを抽出
        # これは簡易的な実装

        result = {
            "status": "executed",
            "state": self.state,
            "stack": self.stack
        }

        return result

    def call_function(self, function_name: str, *args) -> Any:
        """
        JCross関数を呼び出す

        Args:
            function_name: 関数名
            *args: 引数

        Returns:
            戻り値
        """
        if function_name in self.functions:
            return self.functions[function_name](*args)

        raise ValueError(f"Unknown function: {function_name}")

    def get_state(self, key: str) -> Any:
        """状態を取得"""
        return self.state.get(key)

    def set_state(self, key: str, value: Any):
        """状態を設定"""
        self.state[key] = value


class ZeroYearOldJCross:
    """
    0歳児モデル（JCross版）

    zero_year_old_complete.jcrossを実行するラッパー。
    """

    def __init__(self):
        """Initialize"""
        self.runtime = JCrossRuntime()

        # JCrossファイルをロード
        jcross_file = Path(__file__).parent.parent / "vision" / "zero_year_old_complete.jcross"

        print("🧠 0歳児モデル（JCross版）起動中...")
        print(f"   JCrossファイル: {jcross_file}")

        # ロード（簡易版）
        self._load_jcross_model(jcross_file)

        print("✅ 起動完了")

    def _load_jcross_model(self, jcross_file: Path):
        """JCrossモデルをロード"""
        # NOTE: 本来はJCrossファイルをパースして実行するが、
        # ブートストラップ版では、Pythonで状態を直接作成

        # 遺伝子公理
        self.runtime.set_state("DNA.恒常性", {
            "体温": {"目標": 37.0, "最小": 36.0, "最大": 38.0, "臨界最小": 35.0, "臨界最大": 40.0},
            "エネルギー": {"目標": 100.0, "最小": 30.0, "最大": 100.0, "臨界最小": 0.0, "臨界最大": 150.0},
            "痛み": {"目標": 0.0, "最小": 0.0, "最大": 10.0, "臨界最小": 0.0, "臨界最大": 100.0},
            "酸素": {"目標": 100.0, "最小": 90.0, "最大": 100.0, "臨界最小": 70.0, "臨界最大": 100.0}
        })

        self.runtime.set_state("生理.状態", {
            "体温": 37.0,
            "エネルギー": 100.0,
            "痛み": 0.0,
            "酸素": 100.0
        })

        # 記憶
        self.runtime.set_state("記憶", {
            "経験": {},
            "クラスタ": {},
            "次ID": 0,
            "次クラスタID": 0,
            "不快感解決ペア": []
        })

        # 学習
        self.runtime.set_state("学習", {
            "前回経験ID": None,
            "前回不快感": 0.0,
            "学習率": 0.01,
            "不快感閾値": 0.3,
            "改善閾値": 0.5,
            "イベント": []
        })

        # 関数を登録
        self.runtime.functions["不快感"] = self._calc_discomfort
        self.runtime.functions["総不快感"] = self._calc_total_discomfort
        self.runtime.functions["反射"] = self._get_reflex
        self.runtime.functions["生存"] = self._is_alive
        self.runtime.functions["記憶する"] = self._store_experience
        self.runtime.functions["観察学習"] = self._observe_and_learn
        self.runtime.functions["経験"] = self._experience
        self.runtime.functions["恒常性変更"] = self._change_homeostasis
        self.runtime.functions["状態"] = self._get_status

    def _calc_discomfort(self, variable: str) -> float:
        """不快感を計算"""
        state = self.runtime.get_state("生理.状態")
        targets = self.runtime.get_state("DNA.恒常性")

        current = state[variable]
        spec = targets[variable]

        # 正常範囲内？
        if spec["最小"] <= current <= spec["最大"]:
            return 0.0

        # 臨界？
        if current <= spec["臨界最小"] or current >= spec["臨界最大"]:
            return 1.0

        # 線形補間
        deviation = abs(spec["目標"] - current)

        if current < spec["最小"]:
            range_size = spec["最小"] - spec["臨界最小"]
        else:
            range_size = spec["臨界最大"] - spec["最大"]

        discomfort = deviation / range_size if range_size > 0 else 0.0
        return max(0.0, min(1.0, discomfort))

    def _calc_total_discomfort(self) -> Dict[str, Any]:
        """総不快感を計算"""
        d_temp = self._calc_discomfort("体温")
        d_energy = self._calc_discomfort("エネルギー")
        d_pain = self._calc_discomfort("痛み")
        d_oxygen = self._calc_discomfort("酸素")

        # エネルギーと酸素は2倍の重み
        total = (d_temp + d_energy * 2 + d_pain + d_oxygen * 2) / 6.0

        state = self.runtime.get_state("生理.状態")
        critical = state["エネルギー"] <= 0 or state["酸素"] <= 70

        return {
            "総不快感": total,
            "臨界": critical,
            "詳細": {
                "体温": d_temp,
                "エネルギー": d_energy,
                "痛み": d_pain,
                "酸素": d_oxygen
            }
        }

    def _get_reflex(self) -> Optional[str]:
        """生存反射を取得"""
        discomfort_info = self._calc_total_discomfort()
        state = self.runtime.get_state("生理.状態")

        if discomfort_info["臨界"]:
            return "cry_critical"
        if discomfort_info["総不快感"] > 0.7:
            return "cry"
        if state["エネルギー"] < 30:
            return "sleep"
        if state["酸素"] < 90:
            return "breathe"
        if state["痛み"] > 10:
            return "avoid"

        return None

    def _is_alive(self) -> bool:
        """生存判定"""
        state = self.runtime.get_state("生理.状態")
        return state["エネルギー"] > 0 and state["酸素"] > 70

    def _store_experience(self, cross_structure: Dict, discomfort: float, context: Dict) -> int:
        """経験を保存"""
        memory = self.runtime.get_state("記憶")

        exp_id = memory["次ID"]
        memory["次ID"] += 1

        # 簡易的な特徴抽出
        features = self._extract_features(cross_structure)

        experience = {
            "ID": exp_id,
            "時刻": time.time(),
            "Cross": cross_structure,
            "特徴": features,
            "不快感": discomfort,
            "コンテキスト": context,
            "解決": None,
            "意味": None
        }

        memory["経験"][exp_id] = experience

        return exp_id

    def _extract_features(self, cross_structure: Dict) -> list:
        """Cross構造から特徴を抽出"""
        # 簡易版: Layer4の情報を抽出
        if "layers" not in cross_structure or len(cross_structure["layers"]) < 5:
            return []

        # メタデータのみ使用（簡易版）
        return [cross_structure.get("metadata", {}).get("total_points", 0)]

    def _observe_and_learn(self, cross_structure: Dict, context: Dict) -> Optional[Dict]:
        """観察して学習"""
        # 現在の不快感
        discomfort_info = self._calc_total_discomfort()
        current_discomfort = discomfort_info["総不快感"]

        # 経験を記憶
        exp_id = self._store_experience(cross_structure, current_discomfort, context)

        learning_state = self.runtime.get_state("学習")
        learning_event = None

        # 前回経験があり、不快だった？
        if learning_state["前回経験ID"] is not None and learning_state["前回不快感"] > learning_state["不快感閾値"]:
            # 改善度
            improvement = learning_state["前回不快感"] - current_discomfort

            # 十分な改善？
            if improvement > learning_state["改善閾値"]:
                # 学習発生！
                learning_event = {
                    "経験ID": exp_id,
                    "不快感前": learning_state["前回不快感"],
                    "不快感後": current_discomfort,
                    "改善": improvement,
                    "重み変化": learning_state["学習率"] * improvement
                }

                # 前回経験に解決を記録
                memory = self.runtime.get_state("記憶")
                prev_exp = memory["経験"].get(learning_state["前回経験ID"])
                if prev_exp:
                    prev_exp["解決"] = "reduced_by_current"

                # イベント記録
                learning_state["イベント"].append(learning_event)

        # 状態更新
        learning_state["前回経験ID"] = exp_id
        learning_state["前回不快感"] = current_discomfort

        return learning_event

    def _experience(self, cross_structure: Dict, context: Dict) -> Dict:
        """経験する（メインAPI）"""
        # 観察して学習
        learning_event = self._observe_and_learn(cross_structure, context)

        # 不快感・反射・生存
        discomfort_info = self._calc_total_discomfort()
        reflex = self._get_reflex()
        alive = self._is_alive()

        return {
            "不快感": discomfort_info,
            "反射": reflex,
            "学習イベント": learning_event,
            "生存": alive
        }

    def _change_homeostasis(self, variable: str, value: float):
        """恒常性変更"""
        state = self.runtime.get_state("生理.状態")
        state[variable] = value

    def _get_status(self) -> Dict:
        """状態を取得"""
        memory = self.runtime.get_state("記憶")
        learning = self.runtime.get_state("学習")

        return {
            "生理": {
                "状態": self.runtime.get_state("生理.状態"),
                "不快感": self._calc_total_discomfort(),
                "反射": self._get_reflex(),
                "生存": self._is_alive()
            },
            "記憶": {
                "総経験数": len(memory["経験"]),
                "クラスタ数": len(memory["クラスタ"]),
                "解決ペア数": len(memory["不快感解決ペア"])
            },
            "学習": {
                "総イベント数": len(learning["イベント"]),
                "最新イベント": learning["イベント"][-5:] if len(learning["イベント"]) > 0 else []
            }
        }

    # ============================================================
    # Public API
    # ============================================================

    def experience(self, cross_structure: Dict, context: Optional[Dict] = None) -> Dict:
        """経験する"""
        if context is None:
            context = {}
        return self._experience(cross_structure, context)

    def change_homeostasis(self, variable: str, value: float):
        """恒常性を変更"""
        self._change_homeostasis(variable, value)

    def get_status(self) -> Dict:
        """状態を取得"""
        return self._get_status()

    def reset(self):
        """リセット"""
        self._load_jcross_model(None)
