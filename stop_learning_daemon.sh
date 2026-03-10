#!/bin/bash
# Verantyx 継続的学習デーモン停止スクリプト

PID_FILE="$HOME/.verantyx/daemon.pid"

echo ""
echo "🛑 Verantyx 継続的学習デーモン 停止"
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "❌ デーモンは実行されていません"
    exit 1
fi

DAEMON_PID=$(cat "$PID_FILE")

if ! ps -p "$DAEMON_PID" > /dev/null 2>&1; then
    echo "⚠️  プロセスが見つかりません (PID: $DAEMON_PID)"
    rm -f "$PID_FILE"
    exit 1
fi

echo "プロセス停止中... (PID: $DAEMON_PID)"
kill -TERM "$DAEMON_PID"

# 終了を待つ（最大10秒）
for i in {1..10}; do
    if ! ps -p "$DAEMON_PID" > /dev/null 2>&1; then
        echo "✅ デーモン停止完了"
        rm -f "$PID_FILE"
        echo ""
        exit 0
    fi
    sleep 1
done

# まだ実行中なら強制終了
echo "⚠️  強制終了中..."
kill -KILL "$DAEMON_PID"
rm -f "$PID_FILE"
echo "✅ 強制停止完了"
echo ""
