#!/usr/bin/env python3
"""
拡張されたJCross命令のテスト

繰り返し、追加、条件分岐、動的ラベル生成をテスト
"""

from production_jcross_engine import 本番JCrossエンジン


def テスト_繰り返し命令():
    """繰り返し命令のテスト"""
    print("=" * 80)
    print("【テスト1】繰り返し命令")
    print("=" * 80)
    print()

    エンジン = 本番JCrossエンジン()

    テストコード = """
# グローバル変数
生成する テストリスト = ["りんご", "バナナ", "オレンジ"]
生成する 結果 = []

ラベル 繰り返しテスト
  出力する "=== 繰り返しテスト開始 ==="

  取り出す テストリスト
  取り出す リスト

  繰り返す 果物 in リスト:
    出力する "果物: " + 果物
    追加する 果物 to 結果
  繰り返し終了

  出力する "=== 繰り返しテスト完了 ==="

  返す 結果
"""

    エンジン._jcrossコードをパース(テストコード)
    結果 = エンジン.ラベルを実行("繰り返しテスト")

    print()
    print(f"結果: {結果}")
    print()


def テスト_条件分岐():
    """条件分岐のテスト"""
    print("=" * 80)
    print("【テスト2】条件分岐")
    print("=" * 80)
    print()

    エンジン = 本番JCrossエンジン()

    テストコード = """
生成する 数値 = 10

ラベル 条件テスト
  出力する "=== 条件分岐テスト開始 ==="

  取り出す 数値
  取り出す 値

  条件 値 == 10:
    出力する "値は10です"
  条件終了

  条件 値 > 5:
    出力する "値は5より大きい"
  条件終了

  条件 値 < 20:
    出力する "値は20より小さい"
  条件終了

  出力する "=== 条件分岐テスト完了 ==="

  返す
"""

    エンジン._jcrossコードをパース(テストコード)
    エンジン.ラベルを実行("条件テスト")
    print()


def テスト_追加命令():
    """追加命令のテスト"""
    print("=" * 80)
    print("【テスト3】追加命令")
    print("=" * 80)
    print()

    エンジン = 本番JCrossエンジン()

    テストコード = """
生成する 配列 = []

ラベル 追加テスト
  出力する "=== 追加テスト開始 ==="

  追加する "要素1" to 配列
  追加する "要素2" to 配列
  追加する "要素3" to 配列

  取り出す 配列
  取り出す 結果

  出力する "配列の長さ: " + 配列

  繰り返す 要素 in 結果:
    出力する "  - " + 要素
  繰り返し終了

  出力する "=== 追加テスト完了 ==="

  返す 結果
"""

    エンジン._jcrossコードをパース(テストコード)
    結果 = エンジン.ラベルを実行("追加テスト")

    print()
    print(f"結果: {結果}")
    print()


def テスト_動的ラベル生成():
    """動的ラベル生成のテスト"""
    print("=" * 80)
    print("【テスト4】動的ラベル生成")
    print("=" * 80)
    print()

    エンジン = 本番JCrossエンジン()

    # 動的にラベルを追加
    新ラベル命令 = [
        '出力する "これは動的に生成されたラベルです"',
        '設定する メッセージ = "動的実行成功"',
        '返す メッセージ'
    ]

    エンジン.ラベルを動的に追加("動的ラベル", 新ラベル命令)

    # 動的ラベルを実行
    結果 = エンジン.ラベルを実行("動的ラベル")

    print()
    print(f"結果: {結果}")
    print()


def テスト_Cross構造操作():
    """Cross構造の操作テスト"""
    print("=" * 80)
    print("【テスト5】Cross構造操作")
    print("=" * 80)
    print()

    エンジン = 本番JCrossエンジン()

    テストコード = """
生成する TestCross = {
  "UP": [],
  "DOWN": [],
  "LEFT": [],
  "RIGHT": [],
  "FRONT": [],
  "BACK": []
}

ラベル Cross操作テスト
  出力する "=== Cross構造操作テスト開始 ==="

  # UP軸に追加
  追加する "抽象概念1" to TestCross.UP
  追加する "抽象概念2" to TestCross.UP

  # DOWN軸に追加
  追加する "具体例1" to TestCross.DOWN
  追加する "具体例2" to TestCross.DOWN

  取り出す TestCross
  取り出す Cross

  出力する "UP軸の要素数: " + Cross

  取り出す Cross.UP
  取り出す UP軸

  繰り返す 要素 in UP軸:
    出力する "  UP: " + 要素
  繰り返し終了

  取り出す Cross.DOWN
  取り出す DOWN軸

  繰り返す 要素 in DOWN軸:
    出力する "  DOWN: " + 要素
  繰り返し終了

  出力する "=== Cross構造操作テスト完了 ==="

  返す Cross
"""

    エンジン._jcrossコードをパース(テストコード)
    結果 = エンジン.ラベルを実行("Cross操作テスト")

    print()
    print(f"結果のCross構造:")
    print(f"  UP: {結果.get('UP', [])}")
    print(f"  DOWN: {結果.get('DOWN', [])}")
    print()


def 全テスト実行():
    """全テストを実行"""
    print()
    print("=" * 80)
    print("🧪 拡張JCross命令テストスイート")
    print("=" * 80)
    print()

    try:
        テスト_繰り返し命令()
    except Exception as e:
        print(f"❌ テスト1失敗: {e}")
        import traceback
        traceback.print_exc()

    try:
        テスト_条件分岐()
    except Exception as e:
        print(f"❌ テスト2失敗: {e}")
        import traceback
        traceback.print_exc()

    try:
        テスト_追加命令()
    except Exception as e:
        print(f"❌ テスト3失敗: {e}")
        import traceback
        traceback.print_exc()

    try:
        テスト_動的ラベル生成()
    except Exception as e:
        print(f"❌ テスト4失敗: {e}")
        import traceback
        traceback.print_exc()

    try:
        テスト_Cross構造操作()
    except Exception as e:
        print(f"❌ テスト5失敗: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("✅ 全テスト完了")
    print("=" * 80)
    print()


if __name__ == "__main__":
    全テスト実行()
