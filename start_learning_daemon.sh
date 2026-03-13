#!/bin/bash
# Background Learning Daemon Startup Script

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DAEMON_SCRIPT="$SCRIPT_DIR/verantyx_cli/daemon/background_learner.py"
PID_FILE="$SCRIPT_DIR/.verantyx/daemon.pid"
LOG_FILE="$SCRIPT_DIR/.verantyx/background_learning.log"

# PIDファイルのディレクトリ作成
mkdir -p "$SCRIPT_DIR/.verantyx"

# 既に実行中かチェック
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  背景学習デーモンは既に実行中です (PID: $OLD_PID)"
        exit 1
    else
        echo "古いPIDファイルを削除"
        rm "$PID_FILE"
    fi
fi

# デーモンを起動
echo "📚 背景学習デーモンを起動中..."
nohup python3 "$DAEMON_SCRIPT" > "$LOG_FILE" 2>&1 &
DAEMON_PID=$!

# PIDを保存
echo "$DAEMON_PID" > "$PID_FILE"

echo "✅ 背景学習デーモンを起動しました"
echo "   PID: $DAEMON_PID"
echo "   ログファイル: $LOG_FILE"
echo ""
echo "停止するには: ./stop_learning_daemon.sh"
