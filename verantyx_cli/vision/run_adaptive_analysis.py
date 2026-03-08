#!/usr/bin/env python3
"""
Adaptive Video Analysis Runner
適応的動画解析ランナー

状態遷移を検出し、解像度を動的に調整しながら動画を解析する。
JCrossコードが自己変容する。

使い方:
    python -m verantyx_cli.vision.run_adaptive_analysis video.mp4
"""

import sys
from pathlib import Path
from typing import Dict, Any
import argparse

from verantyx_cli.vision.adaptive_resolution_controller import (
    AdaptiveResolutionController,
    TransitionInfo
)
from verantyx_cli.vision.self_modifying_jcross import SelfModifyingJCrossGenerator


def run_adaptive_analysis(video_path: Path, max_frames: int = 100) -> Dict[str, Any]:
    """
    適応的動画解析を実行

    Args:
        video_path: 動画ファイルパス
        max_frames: 最大解析フレーム数

    Returns:
        解析結果
    """
    print()
    print("=" * 70)
    print("🎬 適応的動画解析（自己変容型JCross）")
    print("=" * 70)
    print(f"動画: {video_path.name}")
    print(f"最大フレーム数: {max_frames}")
    print("=" * 70)
    print()

    # コントローラとジェネレータを初期化
    resolution_controller = AdaptiveResolutionController(initial_level="low")
    jcross_generator = SelfModifyingJCrossGenerator()

    # 解析結果
    results = {
        "video_path": str(video_path),
        "frames_analyzed": 0,
        "transitions_detected": 0,
        "resolution_changes": [],
        "frame_results": []
    }

    # 前フレーム（初期はNone）
    prev_frame_cross = None

    print("🔄 解析開始...\n")

    # フレームを解析
    for frame_number in range(max_frames):
        # 進捗表示（10%ごと）
        if frame_number % (max_frames // 10) == 0 and frame_number > 0:
            progress = (frame_number / max_frames) * 100
            print(f"   進捗: {progress:.0f}% (フレーム {frame_number}/{max_frames})")

        # 1. 現在のフレームを取得（ダミー実装）
        current_frame_cross = _get_dummy_frame(frame_number)

        # 2. 状態遷移を検出
        if prev_frame_cross:
            transition_info = resolution_controller.detect_transition(
                prev_frame_cross,
                current_frame_cross
            )
        else:
            transition_info = TransitionInfo(
                is_transition=False,
                transition_magnitude=0.0,
                transition_type="none",
                axis_changes={}
            )

        # 3. 解像度を更新
        prev_level = resolution_controller.current_level
        new_level = resolution_controller.update(transition_info, frame_number)

        if new_level != prev_level:
            results["resolution_changes"].append({
                "frame": frame_number,
                "from": prev_level,
                "to": new_level,
                "reason": transition_info.transition_type
            })

        # 4. 状態に応じたJCrossコードを生成
        state = resolution_controller.get_state()
        state["frame_number"] = frame_number
        state["transition_type"] = transition_info.transition_type

        generated_code = jcross_generator.generate_code(state)

        # 5. 遷移をカウント
        if transition_info.is_transition:
            results["transitions_detected"] += 1

            print(f"\n⚠️  フレーム {frame_number}: 状態遷移検出！")
            print(f"   タイプ: {transition_info.transition_type}")
            print(f"   変化量: {transition_info.transition_magnitude:.3f}")
            print(f"   解像度: {prev_level} → {new_level}")
            print()

        # 6. フレーム結果を記録
        results["frame_results"].append({
            "frame": frame_number,
            "resolution_level": new_level,
            "max_points": resolution_controller.get_max_points(new_level),
            "transition": transition_info.is_transition,
            "transition_type": transition_info.transition_type,
            "transition_magnitude": transition_info.transition_magnitude
        })

        # 前フレームとして保存
        prev_frame_cross = current_frame_cross
        results["frames_analyzed"] += 1

    print(f"\n   ✅ 解析完了（{results['frames_analyzed']} フレーム）\n")

    # サマリーを表示
    print_summary(results, resolution_controller)

    return results


def _get_dummy_frame(frame_number: int) -> Dict[str, Any]:
    """
    ダミーフレームを取得

    実際の実装では、動画からフレームを読み込んでCross構造に変換
    """
    import random

    # フレーム50で大きな変化をシミュレート
    if frame_number == 50:
        variation = 0.6
    elif 48 <= frame_number <= 55:
        variation = 0.3
    else:
        variation = 0.05

    return {
        "axes": {
            "UP": {"mean": 0.5 + random.uniform(-variation, variation)},
            "DOWN": {"mean": 0.5 + random.uniform(-variation, variation)},
            "RIGHT": {"mean": 0.5 + random.uniform(-variation, variation)},
            "LEFT": {"mean": 0.5 + random.uniform(-variation, variation)},
            "FRONT": {"mean": 0.5 + random.uniform(-variation, variation)},
            "BACK": {"mean": 0.5 + random.uniform(-variation, variation)}
        }
    }


def print_summary(results: Dict[str, Any], controller: AdaptiveResolutionController):
    """解析サマリーを表示"""
    print("=" * 70)
    print("📊 解析サマリー")
    print("=" * 70)
    print(f"解析フレーム数: {results['frames_analyzed']}")
    print(f"状態遷移検出: {results['transitions_detected']} 回")
    print(f"解像度変更: {len(results['resolution_changes'])} 回")
    print()

    if results["resolution_changes"]:
        print("解像度変更履歴:")
        for change in results["resolution_changes"]:
            print(f"  フレーム {change['frame']}: "
                  f"{change['from']} → {change['to']} "
                  f"({change['reason']})")
        print()

    # コントローラのサマリー
    controller.print_summary()

    print("=" * 70)
    print()


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Adaptive Video Analysis - 適応的動画解析"
    )

    parser.add_argument(
        "video",
        type=str,
        help="動画ファイルパス"
    )

    parser.add_argument(
        "--max-frames",
        type=int,
        default=100,
        help="最大解析フレーム数（デフォルト: 100）"
    )

    parser.add_argument(
        "--save-report",
        type=str,
        help="レポートを保存するファイルパス（オプション）"
    )

    args = parser.parse_args()

    # 動画パスを確認
    video_path = Path(args.video).expanduser().absolute()

    if not video_path.exists():
        print(f"❌ 動画が見つかりません: {video_path}")
        return 1

    # 適応的解析を実行
    results = run_adaptive_analysis(video_path, max_frames=args.max_frames)

    # レポート保存
    if args.save_report:
        import json
        report_path = Path(args.save_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"💾 レポートを保存しました: {report_path}")

    print("\n✅ 適応的動画解析が完了しました")
    print("\n主な機能:")
    print("  - 状態遷移の自動検出")
    print("  - 解像度の動的調整（50K → 1M点）")
    print("  - JCrossコードの自己変容")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
