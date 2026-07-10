"""
computer_control.py — コンピュータ操作 (アプリ/UI/クリック/キー入力)
==============================================================================
エージェントの「手」を画面まで伸ばす層。macOS では:

  - open_app / quit_app : アプリの起動・終了 (AppleScript)
  - ui_elements         : 最前面ウィンドウのボタン等の一覧と座標
                          (System Events = アクセシビリティAPI。OCR不要で正確)
  - click / double_click: 座標クリック (Quartz CGEvent)
  - type_text / hotkey  : キー入力・ショートカット
  - screen_read         : スクショ -> OCR で画面のテキストと座標
                          (vision_memory の視覚層に自動刻印)
  - click_text          : 画面上の文字列を探してクリック (OCR照準)

必要な macOS 権限 (システム設定 > プライバシーとセキュリティ):
  - 画面収録 (screen_read / click_text 用)
  - アクセシビリティ (click / type / ui_elements 用)
"""

import subprocess
import sys
import time

IS_MAC = sys.platform == "darwin"


def _osascript(script, timeout=20):
    p = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "osascript failed")
    return p.stdout.strip()


# ── アプリ操作 ────────────────────────────────────────────────────────────────
def open_app(name):
    _osascript(f'tell application "{name}" to activate')
    time.sleep(1.0)
    return f"activated {name}"


def quit_app(name):
    _osascript(f'tell application "{name}" to quit')
    return f"quit {name}"


def frontmost_app():
    return _osascript(
        'tell application "System Events" to get name of first process whose frontmost is true')


# ── UI 要素列挙 (アクセシビリティ = 座標が正確) ────────────────────────────────
def ui_elements(app_name=None, max_items=40):
    app = app_name or frontmost_app()
    script = f'''
    set out to ""
    tell application "System Events"
        tell process "{app}"
            set w to front window
            repeat with e in (UI elements of w)
                try
                    set r to role of e
                    set t to ""
                    try
                        set t to (title of e as text)
                    end try
                    if t is "" then
                        try
                            set t to (value of e as text)
                        end try
                    end if
                    set p to position of e
                    set s to size of e
                    set out to out & r & "|" & t & "|" & (item 1 of p) & "," & (item 2 of p) & "|" & (item 1 of s) & "," & (item 2 of s) & linefeed
                end try
            end repeat
        end tell
    end tell
    return out'''
    raw = _osascript(script)
    items = []
    for line in raw.splitlines()[:max_items]:
        parts = line.split("|")
        if len(parts) == 4:
            role, title, pos, size = parts
            x, y = pos.split(",")
            w, h = size.split(",")
            cx, cy = int(x) + int(w) // 2, int(y) + int(h) // 2
            items.append({"role": role, "title": title[:60], "center": [cx, cy],
                          "size": [int(w), int(h)]})
    return items


# ── マウス / キーボード (Quartz CGEvent) ─────────────────────────────────────
def _post_mouse(x, y, kind):
    import Quartz
    ev = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def click(x, y, double=False):
    import Quartz
    _post_mouse(x, y, Quartz.kCGEventMouseMoved)
    time.sleep(0.05)
    n = 2 if double else 1
    for i in range(n):
        ev_d = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseDown, (x, y), Quartz.kCGMouseButtonLeft)
        ev_u = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseUp, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventSetIntegerValueField(ev_d, Quartz.kCGMouseEventClickState, i + 1)
        Quartz.CGEventSetIntegerValueField(ev_u, Quartz.kCGMouseEventClickState, i + 1)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_d)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_u)
        time.sleep(0.08)
    return f"clicked ({x:.0f}, {y:.0f})" + (" x2" if double else "")


def type_text(text):
    # AppleScript keystroke は IME を通らないので日本語も clipboard 経由が確実
    script = f'set the clipboard to "{_esc(text)}"\n' \
             'tell application "System Events" to keystroke "v" using command down'
    _osascript(script)
    return f"typed {len(text)} chars"


def hotkey(combo):
    """'cmd+s' 'cmd+shift+t' 'enter' などのショートカット。"""
    parts = [p.strip().lower() for p in combo.split("+")]
    mods = {"cmd": "command down", "command": "command down",
            "shift": "shift down", "alt": "option down", "option": "option down",
            "ctrl": "control down", "control": "control down"}
    used = [mods[p] for p in parts if p in mods]
    key = [p for p in parts if p not in mods]
    key = key[0] if key else ""
    codes = {"enter": 36, "return": 36, "tab": 48, "space": 49, "esc": 53,
             "escape": 53, "delete": 51, "up": 126, "down": 125, "left": 123, "right": 124}
    using = (" using {" + ", ".join(used) + "}") if used else ""
    if key in codes:
        _osascript(f'tell application "System Events" to key code {codes[key]}{using}')
    else:
        _osascript(f'tell application "System Events" to keystroke "{key}"{using}')
    return f"hotkey {combo}"


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ── 画面読み取り (OCR + 視覚層刻印) ───────────────────────────────────────────
def screen_read(imprint=True, label=""):
    """スクショ -> OCR。視覚層に立体十字式で刻印し、テキスト+座標を返す。"""
    from vision_memory import VisionMemory, take_screenshot, ocr_image
    import os
    png = take_screenshot()
    try:
        if imprint:
            vm = VisionMemory()
            node = vm.imprint_screen(png, label=label or f"screen_read {frontmost_app()}")
            items = [(t, x, y) for t, x, y, w, h in
                     [tuple(r) for r in node["L3_ocr"]]]
        else:
            raw, _ = ocr_image(png)
            items = [(t, x, y) for t, x, y, w, h in raw]
    finally:
        if os.path.exists(png):
            os.unlink(png)
    return items


def click_text(query):
    """画面上から文字列を OCR で探してクリック (見つからなければ候補を返す)。"""
    from vision_memory import VisionMemory
    vm = VisionMemory()
    matches = vm.find_on_screen(query)
    if not matches:
        return f"'{query}' not found on screen"
    t, x, y, w, h = matches[0]
    click(x, y)
    return f"clicked '{t}' at ({x:.0f}, {y:.0f})"


if __name__ == "__main__":
    print("frontmost:", frontmost_app())
    for e in ui_elements()[:10]:
        print(" ", e)
