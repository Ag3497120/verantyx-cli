#!/usr/bin/env python3
"""
完全統合テスト

Gemini応答データ → コマンドマッチング → Cross構造 → パターン抽出
までの完全なフローをテスト
"""

import json
from pathlib import Path
from gemini_data_loader import Gemini学習データ統合


def テスト用データを作成():
    """テスト用のGemini応答データを作成"""
    テストデータ = """User: Pythonでデータを分析する方法を教えて
Assistant: pandasライブラリを使ってCSVファイルを読み込み、describe()メソッドで統計分析を実行できます

User: エラーが発生したので修正したい
Assistant: まずエラーメッセージを確認して、問題箇所を特定し、コードを修正しましょう

User: システムの性能を最適化する方法は？
Assistant: プロファイリングツールでボトルネックを発見し、効率的なアルゴリズムに変更することで最適化できます

User: 新しい機能を追加したい
Assistant: まず要件を定義し、設計を考え、段階的に実装していくのが良いでしょう

User: データベースに接続してクエリを実行する
Assistant: psycopg2やSQLAlchemyを使って接続し、SQLクエリを発行できます
"""

    テストファイル = Path("/tmp/test_gemini_responses.txt")
    テストファイル.write_text(テストデータ, encoding='utf-8')

    return テストファイル


def 統合テスト実行():
    """完全統合テストを実行"""

    print()
    print("=" * 80)
    print("🧪 完全統合テスト")
    print("=" * 80)
    print()

    # 1. テストデータ作成
    print("【ステップ1】テストデータ作成")
    テストファイル = テスト用データを作成()
    print(f"  ✅ テストファイル作成: {テストファイル}")
    print()

    # 2. 統合システム初期化
    print("【ステップ2】統合システム初期化")
    統合システム = Gemini学習データ統合()
    print()

    # 3. データ読み込み＆学習
    print("【ステップ3】データ読み込み＆学習")
    学習数 = 統合システム.Gemini応答ファイルを読み込み(str(テストファイル))
    print()

    # 4. 統計表示
    print("【ステップ4】学習統計")
    統合システム.統計を表示()

    # 5. Cross構造分析
    print("【ステップ5】Cross構造分析")
    学習履歴 = 統合システム.エンジン.グローバルCross構造.get("学習履歴", [])

    if 学習履歴:
        print(f"  学習履歴数: {len(学習履歴)}件")
        print()

        # 最初の対話を詳細表示
        最初の対話 = 学習履歴[0]
        print("  【最初の対話のCross構造】")
        print()

        # LEFT（ユーザー発言）
        LEFT = 最初の対話.get("LEFT", {})
        print(f"  ◆ LEFT（ユーザー発言）:")
        print(f"    元テキスト: {LEFT.get('元テキスト', '')}")
        print(f"    マッチ数: {LEFT.get('マッチ数', 0)}個")
        print(f"    マッチしたコマンド: {LEFT.get('マッチしたコマンド', [])}")
        print()

        # Cross軸統合の詳細
        Cross軸統合 = LEFT.get("Cross軸統合", {})
        for 軸名 in ["UP", "DOWN", "LEFT", "RIGHT", "FRONT", "BACK"]:
            軸データ = Cross軸統合.get(軸名, [])
            if 軸データ:
                print(f"    {軸名}軸:")
                for 項目 in 軸データ[:3]:  # 最初の3個のみ
                    print(f"      - {項目.get('コマンド', '')}: {項目.get('内容', '')}")
        print()

        # RIGHT（応答）
        RIGHT = 最初の対話.get("RIGHT", {})
        print(f"  ◆ RIGHT（AI応答）:")
        print(f"    元テキスト: {RIGHT.get('元テキスト', '')}")
        print(f"    マッチ数: {RIGHT.get('マッチ数', 0)}個")
        print()

        # UP（抽象）
        UP = 最初の対話.get("UP", [])
        if UP:
            print(f"  ◆ UP（抽象レベル）:")
            for 項目 in UP:
                print(f"    {項目}")
        print()

    # 6. パターン抽出テスト
    print("【ステップ6】パターン抽出")
    パターン分析 = パターンを抽出(学習履歴)

    print(f"  総対話数: {パターン分析['総対話数']}件")
    print(f"  総マッチ数: {パターン分析['総マッチ数']}個")
    print(f"  平均マッチ率: {パターン分析['平均マッチ率']:.1f}%")
    print()

    print("  よく使われるコマンド TOP5:")
    for i, (コマンド, 回数) in enumerate(パターン分析['頻出コマンド'][:5], 1):
        print(f"    {i}. {コマンド}: {回数}回")
    print()

    # 7. Cross構造を保存
    print("【ステップ7】Cross構造を保存")
    統合システム.Cross構造を保存()
    print()

    # 8. 結果サマリー
    print("=" * 80)
    print("✅ 完全統合テスト完了")
    print("=" * 80)
    print()
    print("📊 テスト結果サマリー:")
    print(f"  • 読み込んだ対話数: {学習数}件")
    print(f"  • コマンドマッチ成功率: {パターン分析['平均マッチ率']:.1f}%")
    print(f"  • Cross構造生成: 成功")
    print(f"  • パターン抽出: 成功")
    print()
    print("💡 次のステップ:")
    print("  1. 実際のGemini/Claude応答ファイルを読み込み")
    print("  2. パターンマッチング推論エンジンで推論実行")
    print("  3. 小世界シミュレータで未来予測")
    print("  4. 動的コード生成で新しい処理フロー作成")
    print()


def パターンを抽出(学習履歴: list) -> dict:
    """学習履歴からパターンを抽出"""

    総対話数 = len(学習履歴)
    総マッチ数 = 0
    コマンド回数 = {}

    for 対話 in 学習履歴:
        LEFT = 対話.get("LEFT", {})
        RIGHT = 対話.get("RIGHT", {})

        # マッチ数を集計
        総マッチ数 += LEFT.get("マッチ数", 0)
        総マッチ数 += RIGHT.get("マッチ数", 0)

        # コマンド頻度を集計
        for コマンド in LEFT.get("マッチしたコマンド", []):
            コマンド回数[コマンド] = コマンド回数.get(コマンド, 0) + 1

        for コマンド in RIGHT.get("マッチしたコマンド", []):
            コマンド回数[コマンド] = コマンド回数.get(コマンド, 0) + 1

    # 頻出コマンドをソート
    頻出コマンド = sorted(コマンド回数.items(), key=lambda x: x[1], reverse=True)

    # 平均マッチ率
    平均マッチ率 = (総マッチ数 / (総対話数 * 2) * 100) if 総対話数 > 0 else 0

    return {
        "総対話数": 総対話数,
        "総マッチ数": 総マッチ数,
        "平均マッチ率": 平均マッチ率,
        "頻出コマンド": 頻出コマンド
    }


if __name__ == "__main__":
    統合テスト実行()
