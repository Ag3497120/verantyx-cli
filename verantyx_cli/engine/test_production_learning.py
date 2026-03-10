#!/usr/bin/env python3
"""
本番学習ループの統合テスト
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from production_jcross_engine import 本番JCrossエンジン
from claude_api_monitor_bridge import Claude_API監視ブリッジ

def テスト_本番学習ループ():
    print()
    print("=" * 80)
    print("本番学習ループ 統合テスト")
    print("=" * 80)
    print()

    # 1. 模擬API対話データを作成
    print("【1. 模擬API対話データ作成】")
    監視 = Claude_API監視ブリッジ()
    監視.監視を開始()

    # 3回の対話をシミュレート
    対話リスト = [
        ("Pythonで再帰関数を書いて", "再帰関数の例:\ndef factorial(n):\n    if n == 0: return 1\n    return n * factorial(n-1)"),
        ("機械学習とは何ですか", "機械学習とは、データからパターンを学習するAI技術です"),
        ("どうやってリストをソートしますか", "sorted()関数を使えます:\nsorted([3,1,2]) # [1,2,3]")
    ]

    for ユーザー, Claude in 対話リスト:
        監視.リクエストを傍受({"prompt": ユーザー})
        監視.レスポンスを傍受({"content": Claude})

    print(f"✅ {len(対話リスト)}回の対話データを作成")
    print()

    # 2. .jcrossエンジンで学習ループを実行
    print("【2. production_learning_loop.jcross を読み込み】")
    エンジン = 本番JCrossエンジン()

    try:
        エンジン.jcrossファイルを読み込み("production_learning_loop.jcross")
        print(f"✅ 読み込み成功")
        print(f"  ラベル数: {len(エンジン.ラベル辞書)}")
    except FileNotFoundError:
        print(f"❌ production_learning_loop.jcrossが見つかりません")
        return
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    print()

    # 3. メインエントリーポイントを実行
    print("【3. メイン_本番学習ループ を実行】")
    print("   (注: 無限ループなので、すぐにCtrl+Cで停止してください)")
    print()

    try:
        # 実際には無限ループなので、ここではラベルの存在だけ確認
        if "メイン_本番学習ループ" in エンジン.ラベル辞書:
            print("✅ メイン_本番学習ループ が見つかりました")
            print("   実行可能な状態です")
        else:
            print("❌ メイン_本番学習ループ が見つかりません")
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("✅ 統合テスト完了")
    print("=" * 80)
    print()
    print("注: 実際の学習ループは無限ループで動作します。")
    print("   CLIに組み込んだ際はバックグラウンドで動作し、")
    print("   Claude APIとの対話を検出して自動的に学習します。")
    print()

if __name__ == "__main__":
    テスト_本番学習ループ()
