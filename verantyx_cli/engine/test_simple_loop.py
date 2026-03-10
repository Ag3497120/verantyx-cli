#!/usr/bin/env python3
"""
単純なループテスト
"""

from production_jcross_engine import 本番JCrossエンジン


def テスト():
    print("単純なループテスト")
    print()

    エンジン = 本番JCrossエンジン()

    # 直接ラベルを登録
    エンジン.変数["テストリスト"] = ["a", "b", "c"]

    命令リスト = [
        '出力する "開始"',
        '設定する リスト = テストリスト',
        '繰り返す 要素 in リスト:',
        '  出力する "要素: " + 要素',
        '繰り返し終了',
        '出力する "完了"',
        '返す'
    ]

    エンジン.ラベル辞書["テスト"] = 命令リスト

    try:
        エンジン.ラベルを実行("テスト")
        print("\n✅ テスト成功")
    except Exception as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    テスト()
