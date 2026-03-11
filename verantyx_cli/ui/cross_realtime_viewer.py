#!/usr/bin/env python3
"""
Cross Realtime Viewer - リアルタイムでCross構造の成長を可視化

ブラウザでCross空間（6軸）の構築をリアルタイムで表示
"""

import json
import time
import threading
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional


class CrossViewerServer(SimpleHTTPRequestHandler):
    """Cross構造を提供するHTTPサーバー"""

    cross_file: Optional[Path] = None

    def do_GET(self):
        """GETリクエスト処理"""
        if self.path == '/':
            # HTMLページを返す
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(get_html_content().encode('utf-8'))

        elif self.path == '/cross-data':
            # Cross構造データを返す（JSON）
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            if CrossViewerServer.cross_file and CrossViewerServer.cross_file.exists():
                try:
                    with open(CrossViewerServer.cross_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.wfile.write(json.dumps(data).encode('utf-8'))
                except Exception as e:
                    error_data = {'error': str(e)}
                    self.wfile.write(json.dumps(error_data).encode('utf-8'))
            else:
                empty_data = {'axes': {}}
                self.wfile.write(json.dumps(empty_data).encode('utf-8'))

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """ログを無効化（静かにする）"""
        pass


def get_html_content() -> str:
    """HTMLコンテンツを生成"""
    return """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verantyx Cross Structure Viewer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            overflow: hidden;
        }

        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            padding: 20px;
        }

        header {
            text-align: center;
            margin-bottom: 20px;
        }

        h1 {
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .subtitle {
            opacity: 0.9;
            margin-top: 10px;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(10px);
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .stat-label {
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }

        .stat-value {
            font-size: 2em;
            font-weight: bold;
        }

        .axes-container {
            flex: 1;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            grid-template-rows: repeat(2, 1fr);
            gap: 15px;
            overflow: hidden;
        }

        .axis-card {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            overflow-y: auto;
            transition: transform 0.3s, box-shadow 0.3s;
        }

        .axis-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 24px rgba(0,0,0,0.3);
        }

        .axis-header {
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .axis-icon {
            font-size: 1.8em;
        }

        .axis-content {
            font-size: 0.9em;
            line-height: 1.6;
        }

        .axis-item {
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 10px;
            animation: fadeIn 0.5s;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .refresh-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 0.9em;
        }

        .pulse {
            animation: pulse 1s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* 軸ごとの色 */
        .axis-FRONT { border-left: 4px solid #3b82f6; }
        .axis-BACK { border-left: 4px solid #8b5cf6; }
        .axis-UP { border-left: 4px solid #10b981; }
        .axis-DOWN { border-left: 4px solid #f59e0b; }
        .axis-LEFT { border-left: 4px solid #ef4444; }
        .axis-RIGHT { border-left: 4px solid #06b6d4; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌟 Verantyx Cross Structure</h1>
            <p class="subtitle">リアルタイムで成長するCross空間（6軸）</p>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total Messages</div>
                <div class="stat-value" id="total-messages">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Responses</div>
                <div class="stat-value" id="total-responses">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Tool Calls</div>
                <div class="stat-value" id="total-tools">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Session Duration</div>
                <div class="stat-value" id="session-duration">0s</div>
            </div>
        </div>

        <div class="axes-container">
            <div class="axis-card axis-FRONT" id="axis-front">
                <div class="axis-header">
                    <span>FRONT</span>
                    <span class="axis-icon">⬆️</span>
                </div>
                <div class="axis-content" id="content-front">
                    <p>現在の会話...</p>
                </div>
            </div>

            <div class="axis-card axis-UP" id="axis-up">
                <div class="axis-header">
                    <span>UP</span>
                    <span class="axis-icon">🔼</span>
                </div>
                <div class="axis-content" id="content-up">
                    <p>ユーザー入力...</p>
                </div>
            </div>

            <div class="axis-card axis-DOWN" id="axis-down">
                <div class="axis-header">
                    <span>DOWN</span>
                    <span class="axis-icon">🔽</span>
                </div>
                <div class="axis-content" id="content-down">
                    <p>Claude応答...</p>
                </div>
            </div>

            <div class="axis-card axis-RIGHT" id="axis-right">
                <div class="axis-header">
                    <span>RIGHT</span>
                    <span class="axis-icon">➡️</span>
                </div>
                <div class="axis-content" id="content-right">
                    <p>ツール呼び出し...</p>
                </div>
            </div>

            <div class="axis-card axis-LEFT" id="axis-left">
                <div class="axis-header">
                    <span>LEFT</span>
                    <span class="axis-icon">⬅️</span>
                </div>
                <div class="axis-content" id="content-left">
                    <p>タイムスタンプ...</p>
                </div>
            </div>

            <div class="axis-card axis-BACK" id="axis-back">
                <div class="axis-header">
                    <span>BACK</span>
                    <span class="axis-icon">⬇️</span>
                </div>
                <div class="axis-content" id="content-back">
                    <p>Raw interactions...</p>
                </div>
            </div>
        </div>

        <div class="refresh-indicator pulse">
            🔄 Auto-refreshing...
        </div>
    </div>

    <script>
        async function fetchCrossData() {
            try {
                const response = await fetch('/cross-data');
                const data = await response.json();
                updateUI(data);
            } catch (error) {
                console.error('Failed to fetch Cross data:', error);
            }
        }

        function updateUI(data) {
            if (!data.axes) return;

            // 統計更新
            const upData = data.axes.UP || {};
            const downData = data.axes.DOWN || {};
            const rightData = data.axes.RIGHT || {};
            const leftData = data.axes.LEFT || {};

            document.getElementById('total-messages').textContent = upData.total_messages || 0;
            document.getElementById('total-responses').textContent = (downData.claude_responses || []).length;
            document.getElementById('total-tools').textContent = (rightData.tool_calls || []).length;
            document.getElementById('session-duration').textContent = formatDuration(leftData.session_duration || 0);

            // 各軸を更新
            updateAxis('FRONT', data.axes.FRONT);
            updateAxis('UP', data.axes.UP);
            updateAxis('DOWN', data.axes.DOWN);
            updateAxis('RIGHT', data.axes.RIGHT);
            updateAxis('LEFT', data.axes.LEFT);
            updateAxis('BACK', data.axes.BACK);
        }

        function updateAxis(axisName, axisData) {
            const contentId = `content-${axisName.toLowerCase()}`;
            const contentEl = document.getElementById(contentId);
            if (!contentEl || !axisData) return;

            let html = '';

            // 軸ごとの表示ロジック
            if (axisName === 'FRONT') {
                const conversations = axisData.current_conversation || [];
                html = conversations.slice(-5).map(msg =>
                    `<div class="axis-item">${truncate(JSON.stringify(msg), 100)}</div>`
                ).join('');
            } else if (axisName === 'UP') {
                const inputs = axisData.user_inputs || [];
                html = inputs.slice(-5).map(input =>
                    `<div class="axis-item">💬 ${truncate(input, 80)}</div>`
                ).join('');
            } else if (axisName === 'DOWN') {
                const responses = axisData.claude_responses || [];
                html = responses.slice(-5).map(resp =>
                    `<div class="axis-item">🤖 ${truncate(resp, 80)}</div>`
                ).join('');
            } else if (axisName === 'RIGHT') {
                const tools = axisData.tool_calls || [];
                html = tools.slice(-5).map(tool =>
                    `<div class="axis-item">🔧 ${truncate(JSON.stringify(tool), 80)}</div>`
                ).join('');
            } else if (axisName === 'LEFT') {
                const timestamps = axisData.timestamps || [];
                html = timestamps.slice(-5).map(ts =>
                    `<div class="axis-item">⏰ ${new Date(ts * 1000).toLocaleTimeString()}</div>`
                ).join('');
            } else if (axisName === 'BACK') {
                const interactions = axisData.raw_interactions || [];
                html = interactions.slice(-5).map(interaction =>
                    `<div class="axis-item">${truncate(JSON.stringify(interaction), 80)}</div>`
                ).join('');
            }

            if (html) {
                contentEl.innerHTML = html;
            } else {
                contentEl.innerHTML = '<p style="opacity: 0.5;">データなし</p>';
            }
        }

        function truncate(str, maxLen) {
            if (str.length <= maxLen) return str;
            return str.substring(0, maxLen) + '...';
        }

        function formatDuration(seconds) {
            if (seconds < 60) return Math.floor(seconds) + 's';
            if (seconds < 3600) return Math.floor(seconds / 60) + 'm';
            return Math.floor(seconds / 3600) + 'h';
        }

        // 初回ロード
        fetchCrossData();

        // 1秒ごとに更新
        setInterval(fetchCrossData, 1000);
    </script>
</body>
</html>
"""


def start_viewer_server(cross_file: Path, port: int = 8765) -> threading.Thread:
    """
    Cross構造ビューアーサーバーを起動

    Args:
        cross_file: Cross構造ファイルのパス
        port: サーバーポート

    Returns:
        サーバースレッド
    """
    CrossViewerServer.cross_file = cross_file

    server = HTTPServer(('localhost', port), CrossViewerServer)

    def serve():
        print(f"  🌐 Cross Viewer Server started at http://localhost:{port}")
        print(f"  📂 Watching: {cross_file}")
        print()
        server.serve_forever()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    return thread


def open_cross_viewer(cross_file: Path, port: int = 8765, auto_open_browser: bool = True):
    """
    Cross構造ビューアーを起動してブラウザを開く

    Args:
        cross_file: Cross構造ファイルのパス
        port: サーバーポート
        auto_open_browser: 自動でブラウザを開くか
    """
    print()
    print("=" * 70)
    print("  🌟 Verantyx Cross Structure Realtime Viewer")
    print("=" * 70)
    print()

    # サーバー起動
    thread = start_viewer_server(cross_file, port)

    # 少し待機
    time.sleep(1)

    # ブラウザを開く
    if auto_open_browser:
        url = f"http://localhost:{port}"
        print(f"  🌐 Opening browser: {url}")
        print()
        webbrowser.open(url)

    print("  ℹ️  Press Ctrl+C to stop the viewer")
    print()

    try:
        # メインスレッドを維持
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("  👋 Cross Viewer stopped")
        print()


if __name__ == "__main__":
    # テスト
    import sys

    if len(sys.argv) > 1:
        cross_file = Path(sys.argv[1])
    else:
        cross_file = Path(".verantyx/conversation.cross.json")

    if not cross_file.exists():
        print(f"❌ Cross file not found: {cross_file}")
        sys.exit(1)

    open_cross_viewer(cross_file)
