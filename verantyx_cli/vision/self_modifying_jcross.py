#!/usr/bin/env python3
"""
Self-Modifying JCross Generator
JCross自己変容生成器

現在の状態に応じてJCrossコードを動的に生成・変更する。
"""

from typing import Dict, Any, List, Optional


class SelfModifyingJCrossGenerator:
    """JCrossコード自己変容生成器"""

    def __init__(self):
        self.code_history = []

    def generate_code(
        self,
        state: Dict[str, Any]
    ) -> str:
        """
        現在の状態に応じてJCrossコードを動的生成

        Args:
            state: {
                "resolution_level": str,
                "max_points": int,
                "transition_active": bool,
                "transition_type": str,
                "frame_number": int,
                "focus_regions": List[bbox] (optional)
            }

        Returns:
            JCrossコード（文字列）
        """
        code_lines = []

        # ヘッダー
        code_lines.append("# ============================================")
        code_lines.append("# 自動生成されたJCrossコード")
        code_lines.append(f"# フレーム: {state.get('frame_number', 0)}")
        code_lines.append(f"# 解像度: {state.get('resolution_level', 'low')}")
        code_lines.append(f"# 遷移: {state.get('transition_active', False)}")
        code_lines.append("# ============================================")
        code_lines.append("")

        # 1. フレーム変換（適応的解像度）
        code_lines.extend(self._generate_frame_conversion(state))
        code_lines.append("")

        # 2. 遷移検出コード
        if state.get("transition_active"):
            code_lines.extend(self._generate_transition_handling(state))
            code_lines.append("")

        # 3. 詳細解析コード（高解像度時）
        if self._is_high_resolution(state.get("resolution_level")):
            code_lines.extend(self._generate_detailed_analysis(state))
            code_lines.append("")

        # 4. 焦点領域解析（指定されている場合）
        if state.get("focus_regions"):
            code_lines.extend(self._generate_focus_region_analysis(state))
            code_lines.append("")

        # 5. 差分計算
        code_lines.extend(self._generate_diff_calculation())
        code_lines.append("")

        # 6. 結果保存
        code_lines.extend(self._generate_result_storage(state))

        generated_code = "\n".join(code_lines)

        # 履歴に保存
        self.code_history.append({
            "frame": state.get("frame_number", 0),
            "code": generated_code,
            "state": state.copy()
        })

        return generated_code

    def _generate_frame_conversion(self, state: Dict[str, Any]) -> List[str]:
        """フレーム変換コードを生成"""
        max_points = state.get("max_points", 50000)
        resolution_level = state.get("resolution_level", "low")

        return [
            f"# フレーム変換（解像度: {resolution_level}）",
            f"実行する convert.frame = {{",
            f"  \"max_points\": {max_points},",
            f"  \"quality\": \"{resolution_level}\",",
            f"  \"downsample_factor\": 1",
            f"}}",
            f"入れる current_frame",
            f"捨てる"
        ]

    def _generate_transition_handling(self, state: Dict[str, Any]) -> List[str]:
        """遷移ハンドリングコードを生成"""
        transition_type = state.get("transition_type", 'unknown')

        code = [
            f"# 状態遷移検出モード（タイプ: {transition_type}）",
            f"",
            f"# 詳細解析を有効化",
            f"実行する analyze.detail = {{",
            f"  \"enable\": true,",
            f"  \"precision\": \"high\"",
            f"}}",
            f"入れる detail_result",
            f"捨てる"
        ]

        if transition_type == "sudden":
            code.extend([
                f"",
                f"# 急激な変化 → オブジェクト追跡を強化",
                f"実行する track.objects = {{",
                f"  \"enable\": true,",
                f"  \"method\": \"dense\",",
                f"  \"tracking_precision\": \"high\"",
                f"}}",
                f"入れる tracking_result",
                f"捨てる"
            ])

        return code

    def _generate_detailed_analysis(self, state: Dict[str, Any]) -> List[str]:
        """詳細解析コードを生成"""
        return [
            f"# 高解像度詳細解析",
            f"",
            f"# 領域検出",
            f"読む current_frame",
            f"実行する detect.regions = {{",
            f"  \"min_density\": 0.3,",
            f"  \"min_points\": 100",
            f"}}",
            f"入れる detected_regions",
            f"捨てる",
            f"",
            f"# 各領域の詳細解析",
            f"読む detected_regions",
            f"実行する analyze.regions_detail",
            f"入れる regions_detail",
            f"捨てる"
        ]

    def _generate_focus_region_analysis(self, state: Dict[str, Any]) -> List[str]:
        """焦点領域解析コードを生成"""
        focus_regions = state.get("focus_regions", [])
        max_points = state.get("max_points", 50000)

        code = [
            f"# 焦点領域の超高解像度解析",
            f""
        ]

        for i, bbox in enumerate(focus_regions):
            x1, y1, x2, y2 = bbox
            # 焦点領域は2倍の解像度
            region_max_points = max_points * 2

            code.extend([
                f"# 焦点領域 #{i}",
                f"実行する analyze.region = {{",
                f"  \"bbox\": [{x1}, {y1}, {x2}, {y2}],",
                f"  \"max_points\": {region_max_points},",
                f"  \"precision\": \"ultra\"",
                f"}}",
                f"入れる focus_region_{i}",
                f"捨てる",
                f""
            ])

        return code

    def _generate_diff_calculation(self) -> List[str]:
        """差分計算コードを生成"""
        return [
            f"# フレーム間差分計算",
            f"読む prev_frame",
            f"読む current_frame",
            f"実行する calculate.diff",
            f"入れる frame_diff",
            f"捨てる"
        ]

    def _generate_result_storage(self, state: Dict[str, Any]) -> List[str]:
        """結果保存コードを生成"""
        frame_number = state.get("frame_number", 0)

        return [
            f"# 結果を保存",
            f"読む current_frame",
            f"読む frame_diff",
            f"実行する store.result = {{",
            f"  \"frame_number\": {frame_number}",
            f"}}",
            f"入れる stored_result",
            f"捨てる"
        ]

    def _is_high_resolution(self, level: str) -> bool:
        """高解像度レベルかどうか判定"""
        high_levels = ["high", "very_high", "ultra"]
        return level in high_levels

    def get_code_history(self) -> List[Dict[str, Any]]:
        """コード履歴を取得"""
        return self.code_history

    def print_code(self, code: str):
        """生成されたコードを表示"""
        print("\n" + "=" * 60)
        print("生成されたJCrossコード")
        print("=" * 60)
        print(code)
        print("=" * 60 + "\n")
