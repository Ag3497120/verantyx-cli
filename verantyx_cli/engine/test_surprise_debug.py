"""
驚き検出のデバッグ
"""

import numpy as np
from cross_world_simulator import CrossWorldSimulator


def debug_surprise_detection():
    """驚き検出の詳細デバッグ"""

    print("=" * 80)
    print("驚き検出デバッグ")
    print("=" * 80)
    print()

    sim = CrossWorldSimulator(dt=0.1)

    # ボールを追加
    sim.add_object(
        "ball",
        position=np.array([0.0, 0.0, 5.0]),
        velocity=np.array([0.0, 0.0, 0.0])
    )

    print("ステップ1: 通常の落下")
    print(f"  位置: {sim.objects['ball'].position}")
    print(f"  速度: {sim.objects['ball'].velocity}")
    print()

    # 予測を生成
    predicted_pos = sim.predict_next_position("ball")
    print(f"  予測位置: {predicted_pos}")
    print()

    # ステップ実行（速度を変える前）
    sim.step()

    actual_pos = sim.objects["ball"].position
    print(f"  実際の位置: {actual_pos}")

    error = np.linalg.norm(actual_pos - predicted_pos)
    print(f"  誤差: {error:.6f}m")
    print(f"  閾値: {sim.surprise_threshold}m")
    print(f"  驚き検出: {error > sim.surprise_threshold}")
    print(f"  実際の驚きイベント数: {len(sim.surprise_events)}")
    print()

    print("=" * 80)
    print()

    print("ステップ2: 速度を急激に変更")
    print(f"  現在位置: {sim.objects['ball'].position}")
    print(f"  現在速度: {sim.objects['ball'].velocity}")
    print()

    # 速度を急激に変更
    sim.objects["ball"].velocity = np.array([0.0, 0.0, 10.0])
    print(f"  変更後速度: {sim.objects['ball'].velocity}")
    print()

    # 次の予測を生成
    predicted_pos2 = sim.predict_next_position("ball")
    print(f"  予測位置: {predicted_pos2}")
    print()

    # ステップ実行
    sim.step()

    actual_pos2 = sim.objects["ball"].position
    print(f"  実際の位置: {actual_pos2}")

    error2 = np.linalg.norm(actual_pos2 - predicted_pos2)
    print(f"  誤差: {error2:.6f}m")
    print(f"  閾値: {sim.surprise_threshold}m")
    print(f"  驚き検出: {error2 > sim.surprise_threshold}")
    print(f"  実際の驚きイベント数: {len(sim.surprise_events)}")
    print()

    # デバッグ: step()の内部を確認
    print("=" * 80)
    print("step()内部の確認")
    print("=" * 80)
    print()

    print(f"predictions: {sim.predictions}")
    print(f"prediction_errors: {sim.prediction_errors[-5:]}")
    print()


if __name__ == "__main__":
    debug_surprise_detection()
