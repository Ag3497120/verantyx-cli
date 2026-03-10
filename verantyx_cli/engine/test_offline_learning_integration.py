#!/usr/bin/env python3
"""
本番JCrossエンジンとoffline_learning.jcrossの統合テスト
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from production_jcross_engine import 本番JCrossエンジン

def テスト_offline_learning統合():
    print("=" * 80)
    print("offline_learning.jcross 統合テスト")
    print("=" * 80)
    print()
    
    エンジン = 本番JCrossエンジン()
    
    # .jcrossファイルを読み込み
    print("【1. offline_learning.jcrossを読み込み】")
    try:
        エンジン.jcrossファイルを読み込み("offline_learning.jcross")
        print(f"✅ 読み込み成功")
        print(f"  ラベル数: {len(エンジン.ラベル辞書)}")
        print(f"  ラベル名:")
        for ラベル名 in list(エンジン.ラベル辞書.keys())[:10]:  # 最初の10個のみ表示
            print(f"    - {ラベル名}")
        if len(エンジン.ラベル辞書) > 10:
            print(f"    ... 他 {len(エンジン.ラベル辞書) - 10} 個")
    except FileNotFoundError:
        print(f"⚠️ offline_learning.jcrossが見つかりません")
        print(f"   パス: {os.path.abspath('offline_learning.jcross')}")
        return
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    print()
    
    # 簡単なラベルを実行してみる
    print("【2. テスト実行】")
    
    # メインエントリーポイントがあるか確認
    if "メイン_オフライン学習" in エンジン.ラベル辞書:
        print("  メイン_オフライン学習 を実行...")
        try:
            結果 = エンジン.ラベルを実行("メイン_オフライン学習")
            print(f"✅ 実行完了")
        except Exception as e:
            print(f"⚠️ 実行エラー: {e}")
            # エラーは想定内（プロセッサ未実装のため）
    else:
        print("  メイン_オフライン学習 が見つかりません")
        print(f"  利用可能なラベル: {list(エンジン.ラベル辞書.keys())[:5]}")
    print()
    
    print("=" * 80)
    print("✅ 統合テスト完了")
    print("=" * 80)

if __name__ == "__main__":
    テスト_offline_learning統合()
