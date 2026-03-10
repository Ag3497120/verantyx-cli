#!/usr/bin/env python3
"""
成長の証明 - 実際に賢くなることを証明するテスト
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from claude_api_monitor_bridge import Claude_API監視ブリッジ

def テスト_成長証明():
    print()
    print("=" * 80)
    print("🧠 成長の証明テスト")
    print("=" * 80)
    print()

    監視 = Claude_API監視ブリッジ()
    監視.監視を開始()

    # 10回の対話をシミュレート
    対話リスト = [
        ("Pythonで再帰関数を書いて", "再帰関数の例:\ndef factorial(n):\n    if n == 0: return 1\n    return n * factorial(n-1)"),
        ("機械学習とは何ですか", "機械学習とは、データからパターンを学習するAI技術です"),
        ("どうやってリストをソートしますか", "sorted()関数を使えます:\nsorted([3,1,2]) # [1,2,3]"),
        ("Djangoでウェブアプリを作る方法", "Djangoプロジェクトを作成:\ndjango-admin startproject myapp"),
        ("NumPyで配列を作る", "import numpy as np\narr = np.array([1, 2, 3])"),
        ("データベース接続の方法", "SQLAlchemyを使います:\nengine = create_engine('sqlite:///db.sqlite')"),
        ("正規表現で文字列を抽出", "import re\npattern = r'\\d+'\nre.findall(pattern, text)"),
        ("ファイルの読み込み方法", "with open('file.txt', 'r') as f:\n    content = f.read()"),
        ("クラスの定義方法", "class MyClass:\n    def __init__(self):\n        pass"),
        ("例外処理の書き方", "try:\n    risky_operation()\nexcept Exception as e:\n    handle_error(e)"),
    ]

    print("【10回の対話で成長を測定】")
    print()

    for i, (ユーザー, Claude) in enumerate(対話リスト, 1):
        print(f"━━━ 対話 {i}/10 ━━━")
        監視.リクエストを傍受({"prompt": ユーザー})
        監視.レスポンスを傍受({"content": Claude})
        print()

    print("=" * 80)
    print("📊 最終統計")
    print("=" * 80)

    if hasattr(監視, '学習エンジン'):
        統計 = 監視.学習エンジン.統計を取得()
        print(f"✅ 獲得語彙数: {統計['獲得語彙数']}語")
        print(f"✅ 学習回数: {統計['学習回数']}回")
        print(f"✅ 理解深度: {統計['理解深度']}")
        print()
        print("語彙サンプル（最初の20語）:")
        for i, 語彙 in enumerate(統計['語彙一覧'][:20], 1):
            print(f"  {i}. {語彙}")
        print()
        
        if 統計['獲得語彙数'] > 20:
            print("✅ 成長を確認: 20語以上獲得しました！")
            print("   システムは実際に賢くなっています。")
        else:
            print("⚠️ 語彙獲得が少ない可能性があります")
    else:
        print("❌ 学習エンジンが初期化されていません")

    print()
    print("=" * 80)

if __name__ == "__main__":
    テスト_成長証明()
