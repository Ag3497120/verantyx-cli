#!/usr/bin/env python3
"""
mitmproxy セットアップスクリプト

Claude API通信を傍受して /tmp/claude_responses.jsonl に記録
"""

import subprocess
import sys
from pathlib import Path


def check_mitmproxy():
    """mitmproxy がインストールされているか確認"""
    try:
        result = subprocess.run(
            ['mitmdump', '--version'],
            capture_output=True,
            text=True
        )
        print(f"✅ mitmproxy installed: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ mitmproxy not installed")
        return False


def install_mitmproxy():
    """mitmproxy をインストール"""
    print("\n📦 Installing mitmproxy...")
    try:
        subprocess.run(
            ['pip3', 'install', 'mitmproxy'],
            check=True
        )
        print("✅ mitmproxy installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install mitmproxy: {e}")
        return False


def create_mitmproxy_addon():
    """mitmproxy addon を作成"""
    addon_dir = Path.home() / '.verantyx' / 'mitmproxy_config'
    addon_dir.mkdir(parents=True, exist_ok=True)

    addon_file = addon_dir / 'claude_interceptor.py'

    addon_code = '''"""
Claude API Interceptor - mitmproxy addon

Claude API通信を傍受して /tmp/claude_responses.jsonl に記録
"""

import json
from pathlib import Path
from datetime import datetime


class ClaudeInterceptor:
    """Claude API通信を傍受"""

    def __init__(self):
        self.output_file = Path("/tmp/claude_responses.jsonl")
        self.output_file.touch(exist_ok=True)

    def response(self, flow):
        """応答を傍受"""
        # Claude API のURLを検出
        if "api.anthropic.com" in flow.request.pretty_url or \
           "claude.ai" in flow.request.pretty_url:

            try:
                # リクエストとレスポンスを抽出
                request_body = flow.request.content.decode('utf-8', errors='replace')
                response_body = flow.response.content.decode('utf-8', errors='replace')

                # JSONL形式で記録
                entry = {
                    'timestamp': datetime.now().isoformat(),
                    'url': flow.request.pretty_url,
                    'method': flow.request.method,
                    'request': request_body,
                    'response': response_body,
                    'status_code': flow.response.status_code
                }

                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\\n')

                print(f"[INTERCEPTED] {flow.request.method} {flow.request.pretty_url} - {flow.response.status_code}")

            except Exception as e:
                print(f"[ERROR] Failed to intercept: {e}")


addons = [ClaudeInterceptor()]
'''

    addon_file.write_text(addon_code)
    print(f"✅ Created mitmproxy addon: {addon_file}")

    return addon_file


def create_start_script(addon_file: Path):
    """mitmproxy 起動スクリプトを作成"""
    script_file = Path(__file__).parent / 'start_mitmproxy.sh'

    script_content = f'''#!/bin/bash
# mitmproxy 起動スクリプト

echo "🚀 Starting mitmproxy..."
echo "   Addon: {addon_file}"
echo "   Output: /tmp/claude_responses.jsonl"
echo ""
echo "⚠️  Make sure to configure Claude to use proxy:"
echo "   export HTTP_PROXY=http://localhost:8080"
echo "   export HTTPS_PROXY=http://localhost:8080"
echo ""

# JSONLファイルをクリア
> /tmp/claude_responses.jsonl

# mitmproxy を起動（バックグラウンド）
mitmdump -s {addon_file} --listen-port 8080 --ssl-insecure &

MITMPROXY_PID=$!
echo "✅ mitmproxy started (PID: $MITMPROXY_PID)"
echo ""
echo "To stop: kill $MITMPROXY_PID"
'''

    script_file.write_text(script_content)
    script_file.chmod(0o755)

    print(f"✅ Created start script: {script_file}")

    return script_file


def main():
    print("=" * 70)
    print("  📡 mitmproxy Setup for Claude API Interception")
    print("=" * 70)
    print()

    # Step 1: Check/Install mitmproxy
    if not check_mitmproxy():
        print("\n Would you like to install mitmproxy? (y/n): ", end='')
        if input().lower() == 'y':
            if not install_mitmproxy():
                print("\n❌ Setup failed")
                return

    # Step 2: Create addon
    print("\n📝 Creating mitmproxy addon...")
    addon_file = create_mitmproxy_addon()

    # Step 3: Create start script
    print("\n📝 Creating start script...")
    start_script = create_start_script(addon_file)

    # Summary
    print("\n" + "=" * 70)
    print("✅ Setup complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print()
    print("  1. Start mitmproxy:")
    print(f"     ./start_mitmproxy.sh")
    print()
    print("  2. Configure Claude to use proxy:")
    print("     export HTTP_PROXY=http://localhost:8080")
    print("     export HTTPS_PROXY=http://localhost:8080")
    print()
    print("  3. Run Verantyx:")
    print("     python3 -m verantyx_cli chat")
    print()
    print("  4. Check intercepted data:")
    print("     tail -f /tmp/claude_responses.jsonl")
    print()


if __name__ == '__main__':
    main()
