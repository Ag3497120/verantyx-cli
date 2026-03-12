#!/usr/bin/env python3
"""
高度なグラフアプリケーション
Plotly と Dash を使用した最先端のインタラクティブデータ可視化アプリ
"""

import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
import json
import base64
import io


# アプリケーションの初期化
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

app.title = "高度なグラフアプリケーション"


# サンプルデータ生成
def generate_sample_data():
    """サンプルデータを生成"""
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

    return df


# 初期データ
initial_df = generate_sample_data()


# レイアウト定義
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("🎨 高度なグラフアプリケーション", className="text-center mb-4"),
            html.Hr()
        ])
    ]),

    # コントロールパネル
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4("📊 グラフ設定")),
                dbc.CardBody([
                    # グラフタイプ選択
                    html.Label("グラフの種類:", className="fw-bold"),
                    dcc.Dropdown(
                        id='graph-type',
                        options=[
                            {'label': '📈 折れ線グラフ', 'value': 'line'},
                            {'label': '📊 棒グラフ', 'value': 'bar'},
                            {'label': '⭕ 散布図', 'value': 'scatter'},
                            {'label': '🥧 円グラフ', 'value': 'pie'},
                            {'label': '📊 ヒストグラム', 'value': 'histogram'},
                            {'label': '📦 箱ひげ図', 'value': 'box'},
                            {'label': '🔥 ヒートマップ', 'value': 'heatmap'},
                            {'label': '🎯 バブルチャート', 'value': 'bubble'},
                            {'label': '🌐 3D散布図', 'value': '3d_scatter'},
                            {'label': '🌊 3D曲面図', 'value': '3d_surface'},
                            {'label': '📉 エリアチャート', 'value': 'area'},
                            {'label': '🎪 バイオリンプロット', 'value': 'violin'},
                        ],
                        value='line',
                        className="mb-3"
                    ),

                    # X軸選択
                    html.Label("X軸:", className="fw-bold"),
                    dcc.Dropdown(
                        id='x-axis',
                        value='date',
                        className="mb-3"
                    ),

                    # Y軸選択
                    html.Label("Y軸:", className="fw-bold"),
                    dcc.Dropdown(
                        id='y-axis',
                        value='sales',
                        className="mb-3"
                    ),

                    # カラーマップ選択
                    html.Label("カラースキーム:", className="fw-bold"),
                    dcc.Dropdown(
                        id='color-scheme',
                        options=[
                            {'label': 'デフォルト', 'value': 'plotly'},
                            {'label': 'ビビッド', 'value': 'viridis'},
                            {'label': 'プラズマ', 'value': 'plasma'},
                            {'label': 'インファーノ', 'value': 'inferno'},
                            {'label': 'クール', 'value': 'blues'},
                            {'label': 'ウォーム', 'value': 'reds'},
                        ],
                        value='plotly',
                        className="mb-3"
                    ),

                    # アニメーション設定
                    html.Label("アニメーション:", className="fw-bold"),
                    dbc.Checklist(
                        id='animation-toggle',
                        options=[{'label': ' アニメーション有効', 'value': 'enabled'}],
                        value=[],
                        className="mb-3"
                    ),
                ])
            ], className="mb-3"),

            # データ操作
            dbc.Card([
                dbc.CardHeader(html.H4("💾 データ操作")),
                dbc.CardBody([
                    dbc.Button("📁 サンプルデータ読込", id="load-sample", color="primary", className="w-100 mb-2"),
                    dbc.Button("🔄 データ更新", id="refresh-data", color="success", className="w-100 mb-2"),
                    dbc.Button("📤 CSV エクスポート", id="export-csv", color="info", className="w-100 mb-2"),
                    dcc.Download(id="download-csv"),

                    html.Hr(),

                    html.Label("CSV ファイルをアップロード:", className="fw-bold"),
                    dcc.Upload(
                        id='upload-data',
                        children=dbc.Button("📥 CSVファイル選択", color="secondary", className="w-100"),
                        multiple=False
                    ),
                ])
            ], className="mb-3"),

            # 統計分析
            dbc.Card([
                dbc.CardHeader(html.H4("📐 統計分析")),
                dbc.CardBody([
                    dbc.Button("📊 基本統計", id="show-stats", color="warning", className="w-100 mb-2"),
                    dbc.Button("🔗 相関分析", id="show-correlation", color="danger", className="w-100 mb-2"),
                    dbc.Button("📈 回帰分析", id="show-regression", color="dark", className="w-100 mb-2"),
                ])
            ]),

        ], md=3),

        # グラフ表示エリア
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("📈 グラフ表示", className="d-inline"),
                    dbc.Badge("リアルタイム更新", color="success", className="ms-2")
                ]),
                dbc.CardBody([
                    dcc.Graph(
                        id='main-graph',
                        config={
                            'displayModeBar': True,
                            'displaylogo': False,
                            'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'],
                            'toImageButtonOptions': {
                                'format': 'png',
                                'filename': 'graph',
                                'height': 1080,
                                'width': 1920,
                                'scale': 2
                            }
                        },
                        style={'height': '500px'}
                    )
                ])
            ], className="mb-3"),

            # 統計情報表示エリア
            dbc.Card([
                dbc.CardHeader(html.H4("📊 分析結果")),
                dbc.CardBody([
                    html.Div(id='analysis-output', children=[
                        html.P("分析ボタンをクリックして結果を表示", className="text-muted text-center")
                    ])
                ])
            ], className="mb-3"),

            # データテーブル
            dbc.Card([
                dbc.CardHeader(html.H4("📋 データテーブル")),
                dbc.CardBody([
                    html.Div(id='data-table-container')
                ])
            ])
        ], md=9)
    ]),

    # データストア
    dcc.Store(id='data-store', data=initial_df.to_dict('records')),

    # 自動更新用のインターバル
    dcc.Interval(
        id='interval-component',
        interval=5000,  # 5秒ごと
        n_intervals=0,
        disabled=True
    )

], fluid=True, className="p-4")


# コールバック: グラフ更新
@app.callback(
    Output('main-graph', 'figure'),
    [Input('graph-type', 'value'),
     Input('x-axis', 'value'),
     Input('y-axis', 'value'),
     Input('color-scheme', 'value'),
     Input('animation-toggle', 'value'),
     Input('data-store', 'data')]
)
def update_graph(graph_type, x_col, y_col, color_scheme, animation, data):
    """グラフを更新"""
    df = pd.DataFrame(data)

    # カラーマップの設定
    if color_scheme == 'plotly':
        color_map = None
    else:
        color_map = color_scheme

    # グラフタイプに応じて描画
    if graph_type == 'line':
        fig = px.line(df, x=x_col, y=y_col, title=f'{y_col} の推移')
        fig.update_traces(mode='lines+markers')

    elif graph_type == 'bar':
        fig = px.bar(df, x=x_col, y=y_col, title=f'{y_col} の棒グラフ',
                     color=y_col, color_continuous_scale=color_map)

    elif graph_type == 'scatter':
        fig = px.scatter(df, x=x_col, y=y_col, title=f'{x_col} vs {y_col}',
                        color='category' if 'category' in df.columns else None,
                        size='quantity' if 'quantity' in df.columns else None,
                        hover_data=df.columns)

    elif graph_type == 'pie':
        if 'category' in df.columns:
            pie_data = df.groupby('category')[y_col].sum().reset_index()
            fig = px.pie(pie_data, values=y_col, names='category', title=f'{y_col} の割合')
        else:
            fig = go.Figure()

    elif graph_type == 'histogram':
        fig = px.histogram(df, x=y_col, title=f'{y_col} の分布',
                          color='category' if 'category' in df.columns else None)

    elif graph_type == 'box':
        fig = px.box(df, y=y_col, x='category' if 'category' in df.columns else None,
                    title=f'{y_col} の箱ひげ図',
                    color='category' if 'category' in df.columns else None)

    elif graph_type == 'heatmap':
        # 数値列のみを選択
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        corr_matrix = df[numeric_cols].corr()

        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale=color_map or 'RdBu',
            zmid=0
        ))
        fig.update_layout(title='相関ヒートマップ')

    elif graph_type == 'bubble':
        if all(col in df.columns for col in ['sales', 'costs', 'quantity']):
            fig = px.scatter(df, x='sales', y='costs', size='quantity',
                           color='category' if 'category' in df.columns else None,
                           title='バブルチャート: 売上 vs コスト',
                           hover_data=df.columns)
        else:
            fig = go.Figure()

    elif graph_type == '3d_scatter':
        if all(col in df.columns for col in ['sales', 'costs', 'profit']):
            fig = px.scatter_3d(df, x='sales', y='costs', z='profit',
                              color='category' if 'category' in df.columns else None,
                              title='3D散布図',
                              hover_data=df.columns)
        else:
            fig = go.Figure()

    elif graph_type == '3d_surface':
        # サンプル3Dデータを生成
        x = np.linspace(-5, 5, 50)
        y = np.linspace(-5, 5, 50)
        X, Y = np.meshgrid(x, y)
        Z = np.sin(np.sqrt(X**2 + Y**2))

        fig = go.Figure(data=[go.Surface(x=X, y=Y, z=Z, colorscale=color_map or 'Viridis')])
        fig.update_layout(title='3D曲面図', scene=dict(
            xaxis_title='X',
            yaxis_title='Y',
            zaxis_title='Z'
        ))

    elif graph_type == 'area':
        fig = px.area(df, x=x_col, y=y_col, title=f'{y_col} のエリアチャート')

    elif graph_type == 'violin':
        fig = px.violin(df, y=y_col, x='category' if 'category' in df.columns else None,
                       title=f'{y_col} のバイオリンプロット',
                       box=True, points='all')
    else:
        fig = go.Figure()

    # 共通のレイアウト設定
    fig.update_layout(
        template='plotly_white',
        hovermode='closest',
        height=500,
        font=dict(family='Arial, sans-serif', size=12),
        showlegend=True
    )

    return fig


# コールバック: 軸選択肢の更新
@app.callback(
    [Output('x-axis', 'options'),
     Output('y-axis', 'options')],
    Input('data-store', 'data')
)
def update_axis_options(data):
    """軸の選択肢を更新"""
    df = pd.DataFrame(data)
    columns = [{'label': col, 'value': col} for col in df.columns]
    return columns, columns


# コールバック: データテーブル更新
@app.callback(
    Output('data-table-container', 'children'),
    Input('data-store', 'data')
)
def update_table(data):
    """データテーブルを更新"""
    df = pd.DataFrame(data)

    return dash_table.DataTable(
        data=df.head(20).to_dict('records'),
        columns=[{'name': col, 'id': col} for col in df.columns],
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '8px',
            'fontSize': '12px'
        },
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)'
            }
        ],
        page_size=10
    )


# コールバック: サンプルデータ読込
@app.callback(
    Output('data-store', 'data'),
    Input('load-sample', 'n_clicks'),
    prevent_initial_call=True
)
def load_sample_data(n_clicks):
    """サンプルデータを読み込む"""
    return generate_sample_data().to_dict('records')


# コールバック: データ更新
@app.callback(
    Output('data-store', 'data', allow_duplicate=True),
    Input('refresh-data', 'n_clicks'),
    State('data-store', 'data'),
    prevent_initial_call=True
)
def refresh_data(n_clicks, current_data):
    """データを少し変更してリアルタイム更新をシミュレート"""
    df = pd.DataFrame(current_data)

    # 数値列に小さな変動を追加
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = df[col] + np.random.randn(len(df)) * 0.5

    return df.to_dict('records')


# コールバック: CSV エクスポート
@app.callback(
    Output("download-csv", "data"),
    Input("export-csv", "n_clicks"),
    State('data-store', 'data'),
    prevent_initial_call=True
)
def export_csv(n_clicks, data):
    """CSVファイルをエクスポート"""
    df = pd.DataFrame(data)
    return dcc.send_data_frame(df.to_csv, f"graph_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", index=False)


# コールバック: CSV アップロード
@app.callback(
    Output('data-store', 'data', allow_duplicate=True),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    prevent_initial_call=True
)
def upload_csv(contents, filename):
    """CSVファイルをアップロード"""
    if contents is None:
        return dash.no_update

    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return dash.no_update


# コールバック: 基本統計表示
@app.callback(
    Output('analysis-output', 'children'),
    Input('show-stats', 'n_clicks'),
    State('data-store', 'data'),
    prevent_initial_call=True
)
def show_statistics(n_clicks, data):
    """基本統計情報を表示"""
    df = pd.DataFrame(data)
    numeric_df = df.select_dtypes(include=[np.number])

    stats_df = numeric_df.describe().round(2)

    return [
        html.H5("📊 基本統計量", className="mb-3"),
        dash_table.DataTable(
            data=stats_df.reset_index().to_dict('records'),
            columns=[{'name': col, 'id': col} for col in ['index'] + list(stats_df.columns)],
            style_cell={'textAlign': 'left', 'padding': '8px'},
            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'}
        )
    ]


# コールバック: 相関分析
@app.callback(
    Output('analysis-output', 'children', allow_duplicate=True),
    Input('show-correlation', 'n_clicks'),
    State('data-store', 'data'),
    prevent_initial_call=True
)
def show_correlation(n_clicks, data):
    """相関分析を表示"""
    df = pd.DataFrame(data)
    numeric_df = df.select_dtypes(include=[np.number])

    corr_df = numeric_df.corr().round(3)

    return [
        html.H5("🔗 相関係数マトリックス", className="mb-3"),
        dash_table.DataTable(
            data=corr_df.reset_index().to_dict('records'),
            columns=[{'name': col, 'id': col} for col in ['index'] + list(corr_df.columns)],
            style_cell={'textAlign': 'center', 'padding': '8px'},
            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
            style_data_conditional=[
                {
                    'if': {'filter_query': f'{{{col}}} > 0.7', 'column_id': col},
                    'backgroundColor': 'rgb(144, 238, 144)',
                    'color': 'black'
                } for col in corr_df.columns
            ] + [
                {
                    'if': {'filter_query': f'{{{col}}} < -0.7', 'column_id': col},
                    'backgroundColor': 'rgb(255, 182, 193)',
                    'color': 'black'
                } for col in corr_df.columns
            ]
        )
    ]


# コールバック: 回帰分析
@app.callback(
    Output('analysis-output', 'children', allow_duplicate=True),
    Input('show-regression', 'n_clicks'),
    State('data-store', 'data'),
    State('x-axis', 'value'),
    State('y-axis', 'value'),
    prevent_initial_call=True
)
def show_regression(n_clicks, data, x_col, y_col):
    """回帰分析を実行"""
    df = pd.DataFrame(data)

    # 数値列かチェック
    if x_col not in df.select_dtypes(include=[np.number]).columns or \
       y_col not in df.select_dtypes(include=[np.number]).columns:
        return html.P("回帰分析には数値列を選択してください", className="text-warning")

    x = df[x_col].values
    y = df[y_col].values

    # 線形回帰
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    # 回帰直線のグラフ
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode='markers', name='データ点'))
    fig.add_trace(go.Scatter(
        x=x,
        y=slope * x + intercept,
        mode='lines',
        name=f'回帰直線 (y = {slope:.3f}x + {intercept:.3f})',
        line=dict(color='red', width=2)
    ))

    fig.update_layout(
        title=f'線形回帰分析: {x_col} vs {y_col}',
        xaxis_title=x_col,
        yaxis_title=y_col,
        height=400
    )

    return [
        html.H5("📈 線形回帰分析", className="mb-3"),
        dbc.Row([
            dbc.Col([
                html.P([html.Strong("傾き: "), f"{slope:.4f}"]),
                html.P([html.Strong("切片: "), f"{intercept:.4f}"]),
                html.P([html.Strong("相関係数 (R): "), f"{r_value:.4f}"]),
                html.P([html.Strong("決定係数 (R²): "), f"{r_value**2:.4f}"]),
                html.P([html.Strong("p値: "), f"{p_value:.4e}"]),
                html.P([html.Strong("標準誤差: "), f"{std_err:.4f}"]),
            ])
        ]),
        dcc.Graph(figure=fig)
    ]


if __name__ == '__main__':
    print("=" * 60)
    print("🎨 高度なグラフアプリケーション")
    print("=" * 60)
    print("🌐 アプリケーションを起動しています...")
    print("📍 URL: http://127.0.0.1:8050/")
    print("⚡ ブラウザで上記URLを開いてください")
    print("🛑 終了するには Ctrl+C を押してください")
    print("=" * 60)

    app.run_server(debug=True, host='0.0.0.0', port=8050)
