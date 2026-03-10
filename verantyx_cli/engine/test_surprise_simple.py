"""
最小限の驚き検出テスト
"""

import numpy as np
from cross_world_simulator import CrossWorldSimulator


def test_simple():
    """最小限のテスト"""

    print("=" * 80)
    print("最小限の驚き検出テスト")
    print("=" * 80)
    print()

    sim = CrossWorldSimulator(dt=0.1)
    sim.add_object("ball", position=np.array([0.0, 0.0, 5.0]))

    print(f"閾値: {sim.surprise_threshold}m")
    print()

    # ステップ1: 通常のステップ
    print("ステップ1: 通常")
    sim.step()
    print(f"  位置: {sim.objects['ball'].position}")
    print(f"  速度: {sim.objects['ball'].velocity}")
    print(f"  予測誤差: {sim.prediction_errors[-1] if sim.prediction_errors else 'なし'}")
    print(f"  驚きイベント: {len(sim.surprise_events)}")
    print()

    # 驚き注入
    print("驚き注入: 速度を [0, 0, 10] に変更")
    sim.inject_surprise("ball", np.array([0.0, 0.0, 10.0]))
    print(f"  変更後速度: {sim.objects['ball'].velocity}")
    print()

    # ステップ2: 驚きが検出されるはず
    print("ステップ2: 驚き検出されるはず")

    # 手動で予測を確認
    predicted = sim.predict_next_position("ball")
    print(f"  予測位置: {predicted}")

    sim.step()

    actual = sim.objects["ball"].position
    print(f"  実際の位置: {actual}")

    error = np.linalg.norm(actual - predicted)
    print(f"  誤差: {error:.4f}m")
    print(f"  閾値: {sim.surprise_threshold}m")
    print(f"  誤差 > 閾値: {error > sim.surprise_threshold}")
    print()

    print(f"  予測誤差リスト: {sim.prediction_errors[-3:]}")
    print(f"  驚きイベント数: {len(sim.surprise_events)}")

    if len(sim.surprise_events) > 0:
        print("  ✅ 驚きが検出されました！")
        for event in sim.surprise_events:
            print(f"     誤差: {event['error']:.4f}m, 種類: {event['type']}")
    else:
        print("  ❌ 驚きが検出されませんでした")

        # デバッグ情報
        print()
        print("デバッグ情報:")
        print(f"  step()内の予測: {sim.predictions}")


if __name__ == "__main__":
    test_simple()
