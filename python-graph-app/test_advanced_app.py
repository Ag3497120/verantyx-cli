#!/usr/bin/env python3
"""
高度なグラフアプリケーションのテストスクリプト
"""

import sys
import pandas as pd
import numpy as np

def test_imports():
    """必要なモジュールがインポートできるかテスト"""
    print("=" * 60)
    print("📦 モジュールのインポートテスト")
    print("=" * 60)

    modules = [
        ('dash', 'Dash'),
        ('dash', 'dcc'),
        ('dash', 'html'),
        ('dash_bootstrap_components', 'dbc'),
        ('plotly.graph_objects', 'go'),
        ('plotly.express', 'px'),
        ('pandas', 'pd'),
        ('numpy', 'np'),
        ('scipy', 'stats'),
    ]

    all_passed = True
    for module_name, alias in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name:30s} - OK")
        except ImportError as e:
            print(f"❌ {module_name:30s} - FAILED: {e}")
            all_passed = False

    return all_passed


def test_data_generation():
    """データ生成機能のテスト"""
    print("\n" + "=" * 60)
    print("📊 データ生成テスト")
    print("=" * 60)

    try:
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        df = pd.DataFrame({
            'date': dates,
            'sales': np.cumsum(np.random.randn(100)) + 100,
            'costs': np.cumsum(np.random.randn(100)) * 0.7 + 80,
            'profit': np.cumsum(np.random.randn(100)) * 0.3 + 20,
            'category': np.random.choice(['A', 'B', 'C', 'D'], 100),
            'region': np.random.choice(['北', '南', '東', '西'], 100),
            'quantity': np.random.randint(10, 100, 100),
        })

        print(f"✅ データフレーム作成成功")
        print(f"   行数: {len(df)}")
        print(f"   列数: {len(df.columns)}")
        print(f"   列名: {', '.join(df.columns)}")

        return True, df
    except Exception as e:
        print(f"❌ データ生成失敗: {e}")
        return False, None


def test_graph_creation():
    """グラフ作成機能のテスト"""
    print("\n" + "=" * 60)
    print("📈 グラフ作成テスト")
    print("=" * 60)

    import plotly.express as px
    import plotly.graph_objects as go

    try:
        # サンプルデータ
        df = pd.DataFrame({
            'x': [1, 2, 3, 4, 5],
            'y': [10, 15, 13, 17, 20],
            'category': ['A', 'B', 'A', 'B', 'C']
        })

        # 折れ線グラフ
        fig1 = px.line(df, x='x', y='y', title='折れ線グラフテスト')
        print("✅ 折れ線グラフ作成成功")

        # 散布図
        fig2 = px.scatter(df, x='x', y='y', color='category', title='散布図テスト')
        print("✅ 散布図作成成功")

        # 棒グラフ
        fig3 = px.bar(df, x='category', y='y', title='棒グラフテスト')
        print("✅ 棒グラフ作成成功")

        # 3D散布図
        df_3d = pd.DataFrame({
            'x': np.random.randn(50),
            'y': np.random.randn(50),
            'z': np.random.randn(50)
        })
        fig4 = px.scatter_3d(df_3d, x='x', y='y', z='z', title='3D散布図テスト')
        print("✅ 3D散布図作成成功")

        return True
    except Exception as e:
        print(f"❌ グラフ作成失敗: {e}")
        return False


def test_statistics():
    """統計分析機能のテスト"""
    print("\n" + "=" * 60)
    print("📐 統計分析テスト")
    print("=" * 60)

    from scipy import stats

    try:
        # サンプルデータ
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([2, 4, 5, 4, 5])

        # 線形回帰
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        print("✅ 線形回帰分析成功")
        print(f"   傾き: {slope:.4f}")
        print(f"   切片: {intercept:.4f}")
        print(f"   相関係数 (R): {r_value:.4f}")
        print(f"   決定係数 (R²): {r_value**2:.4f}")

        # 相関分析
        df = pd.DataFrame({
            'a': np.random.randn(100),
            'b': np.random.randn(100),
            'c': np.random.randn(100)
        })

        corr = df.corr()
        print("\n✅ 相関行列計算成功")
        print(corr)

        return True
    except Exception as e:
        print(f"❌ 統計分析失敗: {e}")
        return False


def test_csv_operations():
    """CSV読み書きのテスト"""
    print("\n" + "=" * 60)
    print("💾 CSV操作テスト")
    print("=" * 60)

    try:
        # テストデータ作成
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'value': np.random.randn(10)
        })

        # CSV書き込み
        test_file = '/tmp/test_graph_data.csv'
        df.to_csv(test_file, index=False)
        print(f"✅ CSV書き込み成功: {test_file}")

        # CSV読み込み
        df_loaded = pd.read_csv(test_file)
        print(f"✅ CSV読み込み成功")
        print(f"   読み込んだ行数: {len(df_loaded)}")

        # クリーンアップ
        import os
        os.remove(test_file)
        print(f"✅ テストファイル削除完了")

        return True
    except Exception as e:
        print(f"❌ CSV操作失敗: {e}")
        return False


def main():
    """メインテスト実行"""
    print("\n" + "=" * 60)
    print("🎨 高度なグラフアプリケーション - テスト実行")
    print("=" * 60 + "\n")

    results = []

    # テスト実行
    results.append(("モジュールインポート", test_imports()))
    results.append(("データ生成", test_data_generation()[0]))
    results.append(("グラフ作成", test_graph_creation()))
    results.append(("統計分析", test_statistics()))
    results.append(("CSV操作", test_csv_operations()))

    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10s} - {test_name}")

    print("=" * 60)
    print(f"合計: {passed}/{total} テスト通過")

    if passed == total:
        print("\n🎉 すべてのテストに合格しました！")
        print("✅ アプリケーションは正常に動作する準備ができています")
        print("\n起動方法:")
        print("  python advanced_graph_app.py")
        print("  ブラウザで http://127.0.0.1:8050/ にアクセス")
        return 0
    else:
        print("\n⚠️  一部のテストが失敗しました")
        print("必要なパッケージをインストールしてください:")
        print("  pip install -r requirements.txt")
        return 1


if __name__ == '__main__':
    sys.exit(main())
