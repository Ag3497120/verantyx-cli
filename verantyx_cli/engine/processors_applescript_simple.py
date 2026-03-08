"""
AppleScript Processors - Simple version that sends to frontmost Terminal tab
"""

import subprocess


def send_text_to_active_tab(params: dict) -> dict:
    """
    アクティブなターミナルタブにテキストを送信

    入力 (VM varsから読み取り):
        params with __vm_vars__ containing 'text_to_send'

    出力:
        {"success": int}
    """
    vm_vars = params.get('__vm_vars__', {})
    text = vm_vars.get('text_to_send', '')

    print(f"[DEBUG] text_to_send value: '{text}'")

    if not text:
        print(f"[DEBUG] No text to send")
        return {'success': 0}

    # Clean text
    if text.startswith('INPUT:'):
        text = text[6:].strip()
    else:
        text = text.strip()

    if not text:
        print(f"[DEBUG] No text after cleaning")
        return {'success': 0}

    # Escape for AppleScript
    escaped_text = text.replace('\\', '\\\\')
    escaped_text = escaped_text.replace('"', '\\"')
    escaped_text = escaped_text.replace('\n', '\\n')
    escaped_text = escaped_text.replace('\r', '')

    print(f"[DEBUG] Sending: '{escaped_text}'")

    # Simple approach: Send to frontmost Terminal tab
    applescript = f'''
    tell application "Terminal"
        activate
        delay 0.3
    end tell

    tell application "System Events"
        tell process "Terminal"
            keystroke "{escaped_text}"
            delay 0.1
            keystroke return
        end tell
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=5
        )

        print(f"[DEBUG] Return code: {result.returncode}")
        if result.stderr:
            print(f"[DEBUG] Error: {result.stderr}")

        if result.returncode == 0:
            print(f"[DEBUG] Success!")
            return {'success': 1}
        else:
            return {'success': 0}

    except Exception as e:
        print(f"[DEBUG] Exception: {e}")
        return {'success': 0}


def get_applescript_simple_processors():
    """Simple AppleScript processors"""
    return {
        'applescript.send_to_claude': send_text_to_active_tab,
    }
