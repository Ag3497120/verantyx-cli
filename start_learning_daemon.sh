#!/bin/bash
# Verantyx 継続的学習デーモン起動スクリプト

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/.verantyx/daemon_logs"
PID_FILE="$HOME/.verantyx/daemon.pid"

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

# 既に実行中かチェック
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  デーモンは既に実行中です (PID: $OLD_PID)"
        echo ""
        echo "停止するには:"
        echo "  ./stop_learning_daemon.sh"
        exit 1
    fi
fi

echo "=" "================================================================"
echo "🚀 Verantyx 継続的学習デーモン 起動"
echo "=" "================================================================"
echo ""

# バックグラウンドで実行
nohup python3 "$SCRIPT_DIR/verantyx_cli/vision/continuous_learning_daemon.py" \
    > "$LOG_DIR/daemon_$(date +%Y%m%d_%H%M%S).log" 2>&1 &

DAEMON_PID=$!

# PIDを保存
echo $DAEMON_PID > "$PID_FILE"

echo "✅ デーモン起動完了"
echo ""
echo "プロセスID: $DAEMON_PID"
echo "ログファイル: $LOG_DIR/daemon_$(date +%Y%m%d_%H%M%S).log"
echo ""
echo "ログをリアルタイムで見る:"
echo "  tail -f $LOG_DIR/daemon_*.log | tail -1"
echo ""
echo "停止:"
echo "  ./stop_learning_daemon.sh"
echo ""
echo "=" "================================================================"
echo ""
