#!/bin/bash
# mitmproxy 起動スクリプト

echo "🚀 Starting mitmproxy..."
echo "   Addon: /Users/motonishikoudai/.verantyx/mitmproxy_config/claude_interceptor.py"
echo "   Output: /tmp/claude_responses.jsonl"
echo ""
echo "⚠️  Make sure to configure Claude to use proxy:"
echo "   export HTTP_PROXY=http://localhost:8080"
echo "   export HTTPS_PROXY=http://localhost:8080"
echo ""

# JSONLファイルをクリア
> /tmp/claude_responses.jsonl

# mitmproxy を起動（バックグラウンド）
mitmdump -s /Users/motonishikoudai/.verantyx/mitmproxy_config/claude_interceptor.py --listen-port 8080 --ssl-insecure &

MITMPROXY_PID=$!
echo "✅ mitmproxy started (PID: $MITMPROXY_PID)"
echo ""
echo "To stop: kill $MITMPROXY_PID"
