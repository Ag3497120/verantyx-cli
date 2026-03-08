"""
AppleScript Processors - macOS terminal automation
"""

import subprocess


def send_text_to_claude_tab(params: dict) -> dict:
    """
    Claudeタブにテキストを送信（AppleScript経由）

    入力 (VM varsから読み取り):
        params with __vm_vars__ containing 'text_to_send'

    出力:
        {"success": int}  # 1 if sent, 0 if failed
    """
    vm_vars = params.get('__vm_vars__', {})
    text = vm_vars.get('text_to_send', '')

    # デバッグ出力
    print(f"[DEBUG] VM vars keys: {list(vm_vars.keys())}")
    print(f"[DEBUG] text_to_send value: '{text}'")

    if not text:
        print(f"[DEBUG] No text to send - returning failure")
        return {'success': 0}

    # Clean text: remove "INPUT:" prefix and strip whitespace
    if text.startswith('INPUT:'):
        text = text[6:].strip()
    else:
        text = text.strip()

    if not text:
        print(f"[DEBUG] No text after cleaning - returning failure")
        return {'success': 0}

    # Escape for AppleScript:
    # 1. Escape backslashes first
    # 2. Escape double quotes
    # 3. Replace newlines with \\n
    escaped_text = text.replace('\\', '\\\\')
    escaped_text = escaped_text.replace('"', '\\"')
    escaped_text = escaped_text.replace('\n', '\\n')
    escaped_text = escaped_text.replace('\r', '')

    print(f"[DEBUG] Escaped text: '{escaped_text}'")

    # AppleScript to find Claude tab and send text
    # Strategy: Find the tab running "claude" process and activate it
    applescript = f'''
    tell application "Terminal"
        set foundTab to false
        set targetWindow to missing value
        set targetTab to missing value

        repeat with aWindow in windows
            repeat with aTab in tabs of aWindow
                -- Check if this tab is running claude
                set tabProcesses to processes of aTab
                repeat with aProcess in tabProcesses
                    if aProcess contains "claude" then
                        set targetWindow to aWindow
                        set targetTab to aTab
                        set foundTab to true
                        exit repeat
                    end if
                end repeat
                if foundTab then exit repeat
            end repeat
            if foundTab then exit repeat
        end repeat

        if foundTab then
            -- Activate the window and tab
            set frontmost of targetWindow to true
            set selected of targetTab to true
            delay 0.5

            -- Send keystrokes
            tell application "System Events"
                tell process "Terminal"
                    keystroke "{escaped_text}"
                    delay 0.2
                    keystroke return
                end tell
            end tell
        else
            error "Claude tab not found in any Terminal window"
        end if
    end tell
    '''

    print(f"[DEBUG] Sending text to Claude tab: '{text[:50]}...'")

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=5
        )

        print(f"[DEBUG] AppleScript return code: {result.returncode}")
        if result.stderr:
            print(f"[DEBUG] AppleScript stderr: {result.stderr}")
        if result.stdout:
            print(f"[DEBUG] AppleScript stdout: {result.stdout}")

        if result.returncode == 0:
            print(f"[DEBUG] Successfully sent to Claude tab")
            return {'success': 1}
        else:
            print(f"[DEBUG] AppleScript failed with code {result.returncode}")
            return {'success': 0}
    except Exception as e:
        print(f"[DEBUG] Exception sending to Claude: {e}")
        return {'success': 0}


def get_applescript_processors():
    """AppleScript変換器を返す"""
    return {
        'applescript.send_to_claude': send_text_to_claude_tab,
    }
