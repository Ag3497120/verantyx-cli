"""
Phase 1テスト: 基盤修正の検証

1. 驚き検出バグ修正
2. .jcross統合
"""

import numpy as np
from cross_world_simulator import CrossWorldSimulator
from pathlib import Path


def test_surprise_detection():
    """驚き検出のテスト"""

    print("=" * 80)
    print("【テスト1: 驚き検出】")
    print("=" * 80)
    print()

    sim = CrossWorldSimulator(dt=0.1)

    # ボールを追加
    sim.add_object(
        "ball",
        position=np.array([0.0, 0.0, 5.0]),
        velocity=np.array([0.0, 0.0, 0.0]),
        affordances=["掴める", "投げる"]
    )

    # 1. 通常の落下（驚きなし）
    print("1. 通常の落下（驚きなし）")
    for i in range(10):
        sim.step()

    normal_surprises = len(sim.surprise_events)
    print(f"   驚きイベント: {normal_surprises}回")
    print()

    # 2. 物理法則違反（驚きあり）
    print("2. 物理法則違反: ボールが突然上に飛ぶ")

    # 驚きを注入（外部からの予期しない介入）
    sim.inject_surprise("ball", np.array([0.0, 0.0, 10.0]))

    # 次のステップで驚きが検出されるはず
    sim.step()

    violation_surprises = len(sim.surprise_events) - normal_surprises
    print(f"   驚きイベント: {violation_surprises}回")

    if violation_surprises > 0:
        print("   ✅ 驚き検出成功！")
        for event in sim.surprise_events[-violation_surprises:]:
            print(f"      誤差: {event['error']:.2f}m")
            print(f"      種類: {event['type']}")
    else:
        print("   ❌ 驚き検出失敗")

    print()

    return violation_surprises > 0


def test_jcross_integration():
    """
    .jcross統合のテスト
    """

    print("=" * 80)
    print("【テスト2: .jcross統合】")
    print("=" * 80)
    print()

    # .jcrossファイルのパス
    jcross_file = Path(__file__).parent / "cross_world_simulator.jcross"

    if not jcross_file.exists():
        print("⚠️ cross_world_simulator.jcross が見つかりません")
        print("   デフォルト値でテストします")
        jcross_file = None

    # .jcross設定でシミュレータ作成
    sim = CrossWorldSimulator(dt=0.1, jcross_config_file=str(jcross_file) if jcross_file else None)

    print()
    print(f"読み込んだ設定:")
    print(f"  重力: {sim.gravity} m/s²")
    print(f"  驚き閾値: {sim.surprise_threshold} m")
    print()

    # 設定が適切か確認
    gravity_ok = abs(sim.gravity + 9.8) < 0.1
    threshold_ok = sim.surprise_threshold > 0 and sim.surprise_threshold < 1.0

    if gravity_ok and threshold_ok:
        print("✅ .jcross設定が正しく読み込まれました")
    else:
        print("⚠️ .jcross設定に問題があります")

    print()

    return gravity_ok and threshold_ok


def test_object_permanence():
    """物の永続性のテスト"""

    print("=" * 80)
    print("【テスト3: 物の永続性（再確認）】")
    print("=" * 80)
    print()

    sim = CrossWorldSimulator(dt=0.1)

    # ボールを追加
    sim.add_object(
        "ball",
        position=np.array([1.0, 2.0, 1.0]),
        affordances=["掴める"]
    )

    print("1. ボールを隠す")
    sim.hide_object("ball")

    obj = sim.objects["ball"]
    print(f"   visible: {obj.visible}")
    print(f"   exists: {obj.exists}")
    print()

    print("2. ボールを探す")
    pos = sim.find_object("ball")

    if pos is not None:
        print(f"   見つかった位置: {pos}")
        print("   ✅ 物の永続性が機能しています")
        success = True
    else:
        print("   ❌ ボールが見つかりませんでした")
        success = False

    print()

    return success


def test_learning_from_errors():
    """予測誤差からの学習テスト"""

    print("=" * 80)
    print("【テスト4: 予測誤差からの学習】")
    print("=" * 80)
    print()

    sim = CrossWorldSimulator(dt=0.1)

    # ボールを追加
    sim.add_object(
        "ball",
        position=np.array([0.0, 0.0, 5.0]),
        velocity=np.array([0.0, 0.0, 0.0])
    )

    print("100ステップシミュレーション...")

    for i in range(100):
        sim.step()

    print(f"予測誤差の記録: {len(sim.prediction_errors)}個")

    if len(sim.prediction_errors) > 0:
        avg_error = np.mean(sim.prediction_errors)
        print(f"平均予測誤差: {avg_error:.4f}m")

        if avg_error < 0.01:
            print("✅ 予測精度が高い（誤差 < 1cm）")
            success = True
        else:
            print("⚠️ 予測誤差が大きい")
            success = False
    else:
        print("❌ 予測誤差が記録されていません")
        success = False

    print()

    return success


def run_all_tests():
    """全テストを実行"""

    print("\n")
    print("=" * 80)
    print("Phase 1: 基盤修正 - 統合テスト")
    print("=" * 80)
    print("\n")

    results = {}

    # テスト1: 驚き検出
    results["surprise_detection"] = test_surprise_detection()

    # テスト2: .jcross統合
    results["jcross_integration"] = test_jcross_integration()

    # テスト3: 物の永続性
    results["object_permanence"] = test_object_permanence()

    # テスト4: 学習
    results["learning"] = test_learning_from_errors()

    # 結果サマリー
    print("=" * 80)
    print("テスト結果サマリー")
    print("=" * 80)
    print()

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")

    print()
    print(f"合計: {passed}/{total} テストが成功")
    print()

    if passed == total:
        print("🎉 Phase 1: 基盤修正 - 完全成功！")
        return True
    else:
        print("⚠️ いくつかのテストが失敗しました")
        return False


if __name__ == "__main__":
    success = run_all_tests()

    if success:
        print("\n✅ Phase 1完了。Phase 2（オフライン学習）に進めます。")
    else:
        print("\n❌ 修正が必要です。")
