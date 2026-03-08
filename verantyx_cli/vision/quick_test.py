#!/usr/bin/env python3
"""
Quick Recognition Test
クイック認識テスト

データベース内の全オブジェクトに対する認識精度を素早く確認。

使い方:
    python -m verantyx_cli.vision.quick_test
"""

import sys
from pathlib import Path
from typing import Optional
import argparse

from verantyx_cli.vision.object_cross_database import ObjectCrossDatabase


def quick_test(db_path: Optional[Path] = None):
    """クイックテストを実行"""
    print()
    print("=" * 70)
    print("⚡ Verantyx Vision - Quick Test")
    print("=" * 70)
    print()

    # データベース読み込み
    db = ObjectCrossDatabase(db_path=db_path)

    if not db.objects:
        print("❌ データベースが空です")
        print()
        print("使い方:")
        print("  1. カメラ学習でオブジェクトを登録:")
        print("     python -m verantyx_cli.vision.learn_from_camera")
        print()
        print("  2. 登録後、このテストを実行:")
        print("     python -m verantyx_cli.vision.quick_test")
        return 1

    # データベースサマリー
    db.print_summary()

    # 各オブジェクトの詳細を表示
    print("オブジェクト詳細:")
    print("-" * 70)

    for obj_info in db.list_objects():
        object_name = obj_info['name']
        sample_count = obj_info['sample_count']

        # オブジェクト情報を取得
        obj_detail = db.get_object_info(object_name)

        print(f"\n📦 {object_name}")
        print(f"   サンプル数: {sample_count}")
        print(f"   初回学習: {obj_detail['first_learned'][:19]}")
        print(f"   最終学習: {obj_detail['last_learned'][:19]}")

        # 最新サンプルのCross構造を表示
        latest_sample = obj_detail['samples'][-1]
        cross_struct = latest_sample['cross_structure']

        # 構造タイプを判定
        if 'layers' in cross_struct:
            print(f"   構造: 多層Cross ({cross_struct['metadata']['num_layers']} 層)")
            print(f"   総点数: {cross_struct['metadata']['total_points']:,} 点")

            # 各層の情報
            print("   層構成:")
            for layer in cross_struct['layers']:
                print(f"      Layer {layer['id']}: {layer['name']} ({layer['num_points']:,} 点)")
        elif 'axes' in cross_struct:
            print(f"   構造: 単層Cross")
            axes = cross_struct['axes']
            print(f"   6軸値:")
            for axis_name, axis_data in axes.items():
                mean_val = axis_data.get('mean', 0)
                print(f"      {axis_name:>6}: {mean_val:.3f}")

    print()
    print("-" * 70)

    # 自己認識テスト（学習データで認識テスト）
    print("\n🔍 自己認識テスト（学習データで認識できるか確認）")
    print("-" * 70)
    print()

    total_tests = 0
    total_success = 0

    for object_name in db.objects.keys():
        obj_info = db.get_object_info(object_name)
        samples = obj_info['samples']

        # 各サンプルで認識テスト
        for i, sample in enumerate(samples):
            cross_struct = sample['cross_structure']

            # 認識
            results = db.recognize(cross_struct, top_k=1, min_confidence=0.0)

            total_tests += 1

            if results and len(results) > 0:
                recognized_name = results[0]['object']
                confidence = results[0]['confidence']

                if recognized_name == object_name:
                    total_success += 1
                    status = "✅"
                else:
                    status = "❌"

                print(f"{status} {object_name} サンプル{i+1}: "
                      f"認識結果={recognized_name} ({confidence:.1f}%)")
            else:
                print(f"❌ {object_name} サンプル{i+1}: 認識失敗")

    print()
    print("-" * 70)

    # 統計
    success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0

    print(f"\n総テスト数: {total_tests}")
    print(f"成功数: {total_success}")
    print(f"成功率: {success_rate:.1f}%")
    print()

    # 評価
    if success_rate == 100:
        print("🎉 完璧！全てのサンプルを正しく認識できています")
    elif success_rate >= 90:
        print("🟢 優秀！認識精度は非常に高いです")
    elif success_rate >= 70:
        print("🟡 良好！認識精度は十分ですが、サンプル追加で改善できます")
    elif success_rate >= 50:
        print("🟠 要改善！同じオブジェクトを複数角度から学習してください")
    else:
        print("🔴 要再学習！認識精度が低すぎます")

    print()

    # 推奨事項
    print("推奨事項:")

    if success_rate < 100:
        print("  ❌ 認識できないサンプルがあります")
        print("     → 照明条件や角度を変えて追加学習してください")

    # サンプル数が少ないオブジェクト
    low_sample_objects = [
        obj['name'] for obj in db.list_objects()
        if obj['sample_count'] < 3
    ]

    if low_sample_objects:
        print(f"  📸 サンプル数が少ないオブジェクト: {', '.join(low_sample_objects)}")
        print("     → 複数角度から撮影して精度を向上させてください")

    # オブジェクト数が少ない
    if len(db.objects) < 5:
        print(f"  📦 オブジェクト数が少ない（現在{len(db.objects)}個）")
        print("     → より多くのオブジェクトを学習してください")

    print()

    # 次のステップ
    print("次のステップ:")
    print("  1. 認識精度を向上させる:")
    print("     python -m verantyx_cli.vision.learn_from_camera")
    print("     → 各オブジェクトを3回以上学習")
    print()
    print("  2. カメラで実際にテスト:")
    print("     python -m verantyx_cli.vision.test_all_objects")
    print()
    print("=" * 70)
    print()

    return 0


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Quick Test - データベースのクイックテスト"
    )

    parser.add_argument(
        "--db-path",
        type=str,
        help="データベースパス（デフォルト: ~/.verantyx/object_database.json）"
    )

    args = parser.parse_args()

    # データベースパス
    db_path = None
    if args.db_path:
        db_path = Path(args.db_path).expanduser().absolute()

    return quick_test(db_path=db_path)


if __name__ == "__main__":
    sys.exit(main())
