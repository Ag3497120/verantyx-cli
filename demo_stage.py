#!/usr/bin/env python3
"""
demo_stage.py — デモモード舞台監督 (映像壁 / 窓合わせ転送 / 永遠記憶クローズ)
==============================================================================
・画面を検知し、起動ターミナル用ストリップを確保したうえで役割窓をタイル配置
・転送時は送受信窓を隣接するよう移動してからドア送信 (計算を単純化)
・終了時は永遠記憶への消滅アニメのあと、デモ窓をすべて閉じる
"""
from __future__ import annotations

import json
import os
import platform
import shlex
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PANE = os.path.join(HERE, "demo_pane.py")
BOARD = os.path.join(HERE, "demo_board.py")
BEAM = os.path.join(HERE, "demo_beam.py")
PY = sys.executable

C_WARN = "\033[93m"
C_TITLE = "\033[95m"
C_SYS = "\033[90m"
C_FIN = "\033[92m"
C_RST = "\033[0m"

# 閉じる対象のデモ窓タイトル
DEMO_TITLES = (
    "Commander", "Scout-A", "Scout-B", "Worker-1", "Worker-2",
    "INPUT", "RESULT", "BEAM", "BOARD",
)

DEMO_WARNING = """
╔══════════════════════════════════════════════════════════════════╗
║  DEMO MODE — 使い勝手は意図的に低下します                        ║
╠══════════════════════════════════════════════════════════════════╣
║  ・役割ターミナルを主画面だけの映像壁として配置します          ║
║  ・起動ターミナル(YOU)は下帯に置き、役割窓と重ねません          ║
║  ・転送時は窓を隣接させてからドア送信します                      ║
║  ・exit で永遠記憶アニメのあと全デモ窓を閉じます                 ║
║  ・日常利用は Omni を推奨                                        ║
╚══════════════════════════════════════════════════════════════════╝
"""


def confirm_demo():
    print(f"{C_WARN}{DEMO_WARNING}{C_RST}")
    print(f"{C_TITLE}  デモモードを開始しますか？ 使い勝手が落ちる点を理解した上で。{C_RST}")
    try:
        raw = input("  承認するなら yes / 拒否なら no: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    if raw in ("yes", "y"):
        return True
    print(f"{C_SYS}  デモモードをキャンセルしました。{C_RST}")
    return False


def _cg_main_display_bounds():
    """macOS 主画面のみの (x, y, w, h)。マルチディスプレイでも仮想デスクトップ全体は使わない。
    CoreGraphics 座標。主画面は通常 (0,0,w,h)。"""
    import ctypes
    import ctypes.util
    lib = ctypes.util.find_library("CoreGraphics")
    if not lib:
        return None
    cg = ctypes.CDLL(lib)

    class CGRect(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_double), ("y", ctypes.c_double),
            ("w", ctypes.c_double), ("h", ctypes.c_double),
        ]

    cg.CGMainDisplayID.restype = ctypes.c_uint32
    cg.CGDisplayBounds.restype = CGRect
    cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
    did = cg.CGMainDisplayID()
    b = cg.CGDisplayBounds(did)
    return float(b.x), float(b.y), float(b.w), float(b.h)


def _cg_display_count():
    try:
        import ctypes
        import ctypes.util
        cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
        cg.CGGetActiveDisplayList.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        n = ctypes.c_uint32(0)
        cg.CGGetActiveDisplayList(0, None, ctypes.byref(n))
        return int(n.value)
    except Exception:
        return 1


def detect_screen():
    """主画面だけの usable rect: (x, y, w, h, orient)。

    Terminal の bounds は主画面左上原点。Finder の desktop bounds は
    全ディスプレイ結合になるため使わない。
    """
    if platform.system() == "Darwin":
        try:
            main = _cg_main_display_bounds()
            if main:
                _x, _y, w, h = main
                # 主画面上での Terminal 座標 (左上原点)。メニューバー・Dock を除く
                menu, dock = 28, 10
                x = 0  # 主画面内ローカル
                y = menu
                usable_w = max(640, int(w))
                usable_h = max(480, int(h) - menu - dock)
                orient = "portrait" if usable_h > usable_w else "landscape"
                n = _cg_display_count()
                if n > 1:
                    print(f"{C_SYS}  [Demo] ディスプレイ {n} 台を検出。"
                          f"主画面のみに配置します ({usable_w}×{int(h)})。{C_RST}")
                return x, y, usable_w, usable_h, orient
        except Exception:
            pass
        # フォールバック: 主画面解像度っぽい値 (結合デスクトップは使わない)
        try:
            r = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True, text=True, timeout=8)
            if r.returncode == 0 and r.stdout:
                import json as _json
                data = _json.loads(r.stdout)
                for d in data.get("SPDisplaysDataType", []):
                    for m in d.get("spdisplays_ndrvs", []) or []:
                        res = m.get("_spdisplays_resolution") or m.get("spdisplays_resolution")
                        # e.g. "2304 x 1296"
                        if isinstance(res, str) and "x" in res:
                            parts = res.replace("@", " ").split()
                            nums = [int(p) for p in parts if p.isdigit()]
                            if len(nums) >= 2:
                                w, h = nums[0], nums[1]
                                return 0, 28, w, max(480, h - 38), (
                                    "portrait" if h > w else "landscape")
                        # main only: first entry
                        break
                    break
        except Exception:
            pass
    try:
        import shutil as _sh
        cols, lines = _sh.get_terminal_size((120, 40))
        w, h = max(800, cols * 8), max(600, lines * 16)
    except Exception:
        w, h = 1440, 900
    return 0, 28, w, h, ("portrait" if h > w else "landscape")


def compute_layout(names, screen):
    """起動ターミナル帯を確保し、残りを役割の隙間ゼロ映像壁にする。

    戻り値: bounds dict (roles + LAUNCHER), meta
    """
    sx, sy, sw, sh, orient = screen
    roles = [n for n in names if n not in ("RESULT", "BEAM", "BOARD", "LAUNCHER")]
    preferred = ["Scout-A", "Commander", "Scout-B", "Worker-1", "Worker-2", "INPUT"]
    ordered = [n for n in preferred if n in roles]
    for n in roles:
        if n not in ordered:
            ordered.append(n)
    roles = ordered

    # 起動ターミナル帯: 横画面は下、縦画面は下 (常に下帯で重ならない)
    if orient == "portrait":
        launch_ratio = 0.18
        cols = 2 if len(roles) > 2 else 1
    else:
        launch_ratio = 0.20
        cols = 3 if len(roles) >= 3 else max(1, len(roles))

    launch_h = max(140, int(sh * launch_ratio))
    wall_h = sh - launch_h
    rows = max(1, (len(roles) + cols - 1) // cols) if roles else 1
    cell_w = sw // max(1, cols)
    cell_h = wall_h // max(1, rows)

    out = {}
    for i, name in enumerate(roles):
        r, c = divmod(i, cols)
        x1 = sx + c * cell_w
        y1 = sy + r * cell_h
        next_same_row = (i + 1 < len(roles)) and ((i + 1) // cols == r)
        x2 = sx + sw if not next_same_row else (x1 + cell_w if c < cols - 1 else sx + sw)
        if c == cols - 1:
            x2 = sx + sw
        y2 = sy + wall_h if r == rows - 1 else y1 + cell_h
        out[name] = (int(x1), int(y1), int(x2), int(y2))

    # 起動ターミナル: 下帯全体 (役割と重ならない)
    out["LAUNCHER"] = (int(sx), int(sy + wall_h), int(sx + sw), int(sy + sh))

    centers = {
        n: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for n, b in out.items()
    }
    meta = {
        "screen": {"x": sx, "y": sy, "w": sw, "h": sh, "orient": orient},
        "cols": cols, "rows": rows, "gap": 0,
        "launcher_band": True,
        "centers": {n: [centers[n][0], centers[n][1]] for n in centers},
        "neighbors": {},
    }
    return out, meta


def lerp_bounds(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))


class DemoStage:
    ROLES = ("Commander", "Scout-A", "Scout-B", "Worker-1", "Worker-2")

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="vx_demo_")
        self.logs = {}
        self.fallback = False
        self.board_mode = False
        self._input_hl = os.path.join(self.dir, "INPUT.highlight")
        self._layout_path = os.path.join(self.dir, "layout.json")
        self._opened = False
        self._system = platform.system()
        self.bounds = {}
        self.home_bounds = {}  # 定位置 (転送後に戻す)
        self.meta = {}
        self._launcher_id = None
        self._beam_ready = False
        self._beam_log = os.path.join(self.dir, "BEAM.log")
        self._demo_titles = []
        self._closed = False

    def open(self, extra_names=None):
        names = list(self.ROLES)
        if extra_names:
            for n in extra_names:
                if n not in names:
                    names.append(n)
        # INPUT は映像壁内の状態表示用 (入力自体は LAUNCHER)
        names.append("INPUT")

        for name in names:
            path = os.path.join(self.dir, f"{name}.log")
            open(path, "w").close()
            self.logs[name] = path

        screen = detect_screen()
        self.bounds, self.meta = compute_layout(names, screen)
        self.home_bounds = dict(self.bounds)
        self._save_layout(names)

        if self._system == "Darwin":
            self._launcher_id = self._front_window_id()

        ok = False
        if self._system == "Darwin":
            ok = self._open_macos(names)
        elif self._system == "Windows":
            ok = self._open_windows(names)

        if not ok:
            print(f"{C_WARN}  [Demo] 外部ターミナルを開けませんでした。"
                  f"同一画面フォールバックに切替えます。{C_RST}")
            self.fallback = True
        else:
            if self._system == "Darwin" and not self.board_mode:
                self._ensure_beam()
            # 主画面内に再スナップ + 起動ターミナルを下帯へ (二重適用で確実に)
            time.sleep(0.2)
            for name in names:
                if name in self.home_bounds:
                    self._set_window_bounds_by_title(name, self.home_bounds[name])
            self.place_launcher()
            time.sleep(0.12)
            self.place_launcher()

        self._opened = True
        orient = self.meta.get("screen", {}).get("orient", "?")
        sw = self.meta.get("screen", {}).get("w", 0)
        sh = self.meta.get("screen", {}).get("h", 0)
        lb = self.bounds.get("LAUNCHER")
        self.write("Commander", f"映像壁 {orient} {sw}×{sh} (主画面) — 待機中")
        self.write("INPUT", "◆ 入力は下帯の YOU ターミナルへ")
        if lb:
            print(f"{C_SYS}  [Demo] 起動ターミナル(YOU) → "
                  f"({lb[0]},{lb[1]})-({lb[2]},{lb[3]}) 下帯{C_RST}")
        return self

    def _save_layout(self, names):
        payload = {
            "dir": self.dir,
            "screen": self.meta.get("screen", {}),
            "panes": {
                n: {"bounds": list(self.bounds[n])}
                for n in list(names) + ["LAUNCHER"]
                if n in self.bounds
            },
        }
        with open(self._layout_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _as_str(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _front_window_id(self):
        try:
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "Terminal" to id of front window'],
                capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return int(r.stdout.strip())
        except Exception:
            pass
        return None

    def _macos_window_count(self):
        try:
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "Terminal" to count of windows'],
                capture_output=True, text=True, timeout=5)
            return int((r.stdout or "0").strip() or 0)
        except Exception:
            return 0

    def place_launcher(self):
        """起動ターミナルを下帯へ移動 (役割窓と重ねない)。"""
        if self._system != "Darwin":
            return
        b = self.bounds.get("LAUNCHER")
        if not b:
            return
        x1, y1, x2, y2 = [int(v) for v in b]
        try:
            if self._launcher_id:
                subprocess.run(["osascript", "-e", f'''
tell application "Terminal"
  set miniaturized of window id {self._launcher_id} to false
  set bounds of window id {self._launcher_id} to {{{x1}, {y1}, {x2}, {y2}}}
  try
    set custom title of selected tab of window id {self._launcher_id} to "YOU"
  end try
end tell
'''], capture_output=True, timeout=6)
            else:
                subprocess.run(["osascript", "-e", f'''
tell application "Terminal"
  set bounds of front window to {{{x1}, {y1}, {x2}, {y2}}}
end tell
'''], capture_output=True, timeout=5)
        except Exception:
            pass

    def focus_launcher(self):
        if self._system != "Darwin" or not self._launcher_id:
            return
        try:
            subprocess.run(["osascript", "-e", f'''
tell application "Terminal"
  set miniaturized of window id {self._launcher_id} to false
  set index of window id {self._launcher_id} to 1
  activate
end tell
'''], capture_output=True, timeout=5)
        except Exception:
            pass

    def _pane_cmd(self, name):
        hl = self._input_hl if name == "INPUT" else ""
        return (
            f'"{PY}" "{PANE}" --role "{name}" --log "{self.logs[name]}" '
            f'--title "{name}" --layout "{self._layout_path}"'
            + (f' --highlight-file "{hl}"' if hl else "")
        )

    def _write_command(self, name, cmd):
        script_path = os.path.join(self.dir, f"{name}.command")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write(f'cd "{HERE}"\n')
            f.write(f"exec {cmd}\n")
        os.chmod(script_path, 0o755)
        return script_path

    def _open_macos_window(self, name, script_path, bounds):
        x1, y1, x2, y2 = [int(v) for v in bounds]
        shell = f"/bin/bash {shlex.quote(script_path)}"
        before = self._macos_window_count()
        script = f'''
tell application "Terminal" to activate
delay 0.1
tell application "System Events"
  keystroke "n" using {{command down, option down}}
end tell
delay 0.2
tell application "Terminal"
  set w to front window
  do script {self._as_str(shell)} in selected tab of w
  delay 0.1
  try
    set bounds of w to {{{x1}, {y1}, {x2}, {y2}}}
  end try
  try
    set custom title of selected tab of w to {self._as_str(name)}
  end try
end tell
'''
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "").strip()[:200] or "osascript fail")
        if self._macos_window_count() <= before:
            self._detach_front_tab()
            time.sleep(0.12)
            if self._macos_window_count() <= before:
                raise RuntimeError("window count did not increase")
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "Terminal" to set bounds of front window '
                 f'to {{{x1}, {y1}, {x2}, {y2}}}'],
                capture_output=True, timeout=3)
        except Exception:
            pass
        if name not in self._demo_titles:
            self._demo_titles.append(name)
        return True

    def _detach_front_tab(self):
        script = '''
tell application "Terminal" to activate
try
  tell application "System Events"
    tell process "Terminal"
      if exists menu item "Move Tab to New Window" of menu "Window" of menu bar 1 then
        click menu item "Move Tab to New Window" of menu "Window" of menu bar 1
      else if exists menu item "タブを新しいウインドウに移動" of menu "ウインドウ" of menu bar 1 then
        click menu item "タブを新しいウインドウに移動" of menu "ウインドウ" of menu bar 1
      end if
    end tell
  end tell
end try
'''
        try:
            subprocess.run(["osascript", "-e", script],
                           capture_output=True, timeout=4)
        except Exception:
            pass

    def _set_window_bounds_by_title(self, title, bounds):
        x1, y1, x2, y2 = [int(v) for v in bounds]
        script = f'''
tell application "Terminal"
  repeat with w in windows
    try
      if custom title of selected tab of w is {self._as_str(title)} then
        set bounds of w to {{{x1}, {y1}, {x2}, {y2}}}
        return true
      end if
    end try
  end repeat
  return false
end tell
'''
        try:
            subprocess.run(["osascript", "-e", script],
                           capture_output=True, timeout=4)
        except Exception:
            pass

    def _animate_move(self, title, start, end, steps=5):
        """窓を start→end へ段階移動。"""
        for i in range(1, steps + 1):
            box = lerp_bounds(start, end, i / steps)
            self._set_window_bounds_by_title(title, box)
            time.sleep(0.04)
        self.bounds[title] = tuple(int(v) for v in end)

    def _open_macos_board(self, names):
        roles = ",".join(names)
        cmd = (f'"{PY}" "{BOARD}" --dir "{self.dir}" --roles "{roles}" '
               f'--highlight-file "{self._input_hl}"')
        script_path = self._write_command("BOARD", cmd)
        sc = self.meta["screen"]
        # ボードは壁領域のみ (下帯は LAUNCHER)
        launch = self.bounds.get("LAUNCHER")
        if launch:
            bounds = (sc["x"], sc["y"], sc["x"] + sc["w"], launch[1])
        else:
            bounds = (sc["x"], sc["y"], sc["x"] + sc["w"], sc["y"] + sc["h"])
        try:
            self._open_macos_window("BOARD", script_path, bounds)
            self.board_mode = True
            return True
        except Exception:
            return False

    def _open_macos(self, names):
        opened = 0
        for name in names:
            cmd = self._pane_cmd(name)
            script_path = self._write_command(name, cmd)
            bounds = self.bounds.get(name, (40, 40, 480, 340))
            try:
                self._open_macos_window(name, script_path, bounds)
                opened += 1
            except Exception as e:
                print(f"{C_WARN}  [Demo] 別窓化失敗 ({name}): {str(e)[:100]}{C_RST}")
                break
            time.sleep(0.06)

        if opened == len(names):
            time.sleep(0.15)
            for name in names:
                self._set_window_bounds_by_title(name, self.home_bounds[name])
            return True
        print(f"{C_WARN}  [Demo] 映像壁の複数窓化に失敗。1窓舞台へ。{C_RST}")
        return self._open_macos_board(names)

    def _ensure_beam(self):
        open(self._beam_log, "w").close()
        self.logs["BEAM"] = self._beam_log
        cmd = f'"{PY}" "{BEAM}" --log "{self._beam_log}"'
        script_path = self._write_command("BEAM", cmd)
        try:
            self._open_macos_window("BEAM", script_path, (-800, -800, -400, -600))
            self._beam_ready = True
        except Exception:
            self._beam_ready = False

    def _open_windows(self, names):
        try:
            for name in names:
                subprocess.Popen(
                    ["cmd", "/c", "start", f"VX-{name}", "cmd", "/k",
                     f"cd /d {HERE} && {PY} {PANE} --role {name} "
                     f"--log {self.logs[name]} --title {name} "
                     f"--layout {self._layout_path}"],
                    cwd=HERE)
                self._demo_titles.append(name)
                time.sleep(0.08)
            return True
        except Exception:
            return False

    # ── 描画 / 転送 ───────────────────────────────────────────────────────
    def write(self, role, line):
        path = self.logs.get(role)
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line.rstrip() + "\n")
        if role == "INPUT" or self.fallback:
            color = {"Commander": "\033[95m", "Scout-A": "\033[96m",
                     "Scout-B": "\033[94m", "Worker-1": "\033[92m",
                     "Worker-2": "\033[93m", "INPUT": "\033[97m",
                     "RESULT": "\033[92m"}.get(role, "\033[90m")
            if role == "INPUT" or self.fallback:
                print(f"{color}  [{role:9s}] {line}{C_RST}")

    def ctrl(self, role, kind, **kw):
        payload = {"op": kind, **kw}
        self.write(role, "@json " + json.dumps(payload, ensure_ascii=False))

    def _dock_pair(self, src, dst):
        """送受信窓を画面中央で左右隣接させる bounds を返す。
        常に src=左 / dst=右 → ドアは right→left のみで単純。"""
        sc = self.meta["screen"]
        sx, sy, sw, sh = sc["x"], sc["y"], sc["w"], sc["h"]
        # 下帯を避けた壁領域の中央
        launch = self.bounds.get("LAUNCHER")
        wall_bottom = launch[1] if launch else sy + sh
        wall_h = max(200, wall_bottom - sy)
        dock_h = min(280, int(wall_h * 0.55))
        dock_w = min(420, int(sw * 0.38))
        mid_x = sx + sw / 2
        mid_y = sy + (wall_h - dock_h) / 2
        src_box = (mid_x - dock_w, mid_y, mid_x, mid_y + dock_h)
        dst_box = (mid_x, mid_y, mid_x + dock_w, mid_y + dock_h)
        return (tuple(int(v) for v in src_box),
                tuple(int(v) for v in dst_box))

    def transfer(self, src, dst, label="vector"):
        """窓を隣接させてからドア送信し、定位置へ戻す。"""
        if src not in self.home_bounds or dst not in self.home_bounds:
            self.write(src, f"  ──→ {label} → {dst}")
            self.write(dst, f"  ←── {label} ← {src}")
            return

        pkt = f"⟦{label}⟧"
        home_s = self.home_bounds[src]
        home_d = self.home_bounds[dst]

        if self.board_mode or self.fallback:
            self.ctrl(src, "emit", side="right", packet=pkt, toward=dst)
            time.sleep(0.12)
            self.ctrl(dst, "recv", side="left", packet=pkt, fr=src)
            time.sleep(0.12)
            self.ctrl(src, "door", side="right", state="close")
            self.ctrl(dst, "door", side="left", state="close")
            return

        # 1) 送信窓を合わせるため移動
        self.write(src, f"  ◈ 移動して送信窓を合わせる → {dst}")
        self.write(dst, f"  ◈ 受信位置へ移動 ← {src}")
        dock_s, dock_d = self._dock_pair(src, dst)
        self._animate_move(src, self.bounds.get(src, home_s), dock_s, steps=6)
        self._animate_move(dst, self.bounds.get(dst, home_d), dock_d, steps=6)
        time.sleep(0.08)

        # 2) 隣接ドアで送信 (方向は常に right → left)
        self.ctrl(src, "door", side="right", state="open", toward=dst)
        self.ctrl(src, "emit", side="right", packet=pkt, toward=dst)
        time.sleep(0.12)

        if self._beam_ready:
            self._fly_beam_seam(dock_s, dock_d, pkt)
        else:
            time.sleep(0.1)

        self.ctrl(dst, "door", side="left", state="open", toward=src)
        self.ctrl(dst, "recv", side="left", packet=pkt, fr=src)
        time.sleep(0.15)

        self.ctrl(src, "door", side="right", state="close")
        self.ctrl(dst, "door", side="left", state="close")
        self.write(src, f"  送信完了 {pkt} → {dst}")
        self.write(dst, f"  受信完了 {pkt} ← {src}")

        # 3) 定位置へ復帰
        self._animate_move(src, dock_s, home_s, steps=6)
        self._animate_move(dst, dock_d, home_d, steps=6)

    def _fly_beam_seam(self, src_box, dst_box, pkt):
        """隣接した左右窓の継ぎ目を短く飛ぶ。"""
        y = (src_box[1] + src_box[3]) / 2
        x0 = src_box[2] - 4
        x1 = dst_box[0] + 4
        bw, bh = 160, 70
        with open(self._beam_log, "w", encoding="utf-8") as f:
            f.write(pkt + "\n")
            f.write("dock →\n")
        for i in range(6):
            t = i / 5
            cx = x0 + (x1 - x0) * t
            box = (cx - bw / 2, y - bh / 2, cx + bw / 2, y + bh / 2)
            self._set_window_bounds_by_title("BEAM", box)
            time.sleep(0.035)
        self._set_window_bounds_by_title("BEAM", (-800, -800, -400, -600))

    def highlight_input(self, on=True):
        if on:
            open(self._input_hl, "w").close()
            self.write("INPUT", "▶▶▶ 入力待ち — 下の YOU ターミナルへ")
            self.place_launcher()
            self.focus_launcher()
        else:
            try:
                os.remove(self._input_hl)
            except OSError:
                pass

    def broadcast(self, line):
        for role in self.logs:
            if role in ("RESULT", "BEAM"):
                continue
            self.write(role, line)

    def consensus_banner(self, text):
        bar = "═" * 28
        self.broadcast(f"╔{bar}╗")
        self.broadcast("║ ★ 合意 — ベクトル収束 ★")
        self.broadcast(f"╚{bar}╝")
        time.sleep(0.2)
        for role in self.ROLES:
            if role in self.logs:
                self.ctrl(role, "banner", text=text[:80])
        time.sleep(0.3)
        self.open_result(text)

    def open_result(self, text):
        path = os.path.join(self.dir, "RESULT.log")
        self.logs["RESULT"] = path
        with open(path, "w", encoding="utf-8") as f:
            f.write("━━ FINAL ANSWER ━━\n")
            f.write(text.strip() + "\n")
        if self.fallback or self.board_mode:
            if self.fallback:
                print(f"\n{C_FIN}━━ RESULT ━━\n{text}\n{C_RST}")
            return
        sc = self.meta["screen"]
        launch = self.bounds.get("LAUNCHER")
        top = sc["y"]
        bottom = launch[1] if launch else sc["y"] + sc["h"]
        mx, my = int(sc["w"] * 0.1), int((bottom - top) * 0.1)
        bounds = (sc["x"] + mx, top + my, sc["x"] + sc["w"] - mx, bottom - my)
        self.bounds["RESULT"] = bounds
        cmd = (f'"{PY}" "{PANE}" --role "RESULT" --log "{path}" '
               f'--title "RESULT" --layout "{self._layout_path}"')
        try:
            if self._system == "Darwin":
                sp = self._write_command("RESULT", cmd)
                try:
                    self._open_macos_window("RESULT", sp, bounds)
                except Exception:
                    pass
        except Exception:
            print(f"\n{C_FIN}━━ RESULT ━━\n{text}\n{C_RST}")

    def close(self):
        """永遠記憶への消滅アニメ → 全デモ窓を閉じる。起動ターミナルは残す。"""
        if self._closed:
            return
        self._closed = True
        print(f"\n{C_TITLE}  [Demo] 永遠の記憶へ…{C_RST}")

        # 1) 各ペインに消滅シーケンス
        titles = [t for t in self._demo_titles if t not in ("BEAM",)]
        for phase, msg in enumerate([
            "記憶ベクトルを圧縮しています…",
            "永遠の記憶レイヤへ転送中…",
            "刻印完了 — 消滅します",
        ], 1):
            for role in titles:
                if role in self.logs:
                    self.ctrl(role, "vanish", phase=phase, text=msg)
            self.broadcast(f"◆ {msg}")
            time.sleep(0.35)

        # 2) 窓を画面中央へ収束させながら縮小
        if self._system == "Darwin" and not self.fallback:
            sc = self.meta.get("screen", {})
            cx = sc.get("x", 0) + sc.get("w", 800) / 2
            cy = sc.get("y", 0) + sc.get("h", 600) / 3
            for step in range(1, 7):
                t = step / 6
                size = max(40, 200 * (1 - t))
                box = (cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2)
                for title in list(self._demo_titles):
                    self._set_window_bounds_by_title(title, box)
                time.sleep(0.06)

            # 3) デモ窓をすべて閉じる (YOU / 起動ターミナルは残す)
            self._close_demo_windows()

        print(f"{C_FIN}  [Demo] 全役割ターミナルを閉じました。"
              f"軌跡は永遠の記憶に残ります。{C_RST}")
        print(f"{C_SYS}  [Demo] ログ: {self.dir}{C_RST}")
        self.place_launcher()
        self.focus_launcher()

    def _close_demo_windows(self):
        """タイトル一致のデモ窓を閉じる。LAUNCHER(YOU)は閉じない。"""
        titles = list(dict.fromkeys(self._demo_titles + list(DEMO_TITLES)))
        # AppleScript のリスト
        items = ", ".join(self._as_str(t) for t in titles)
        script = f'''
tell application "Terminal"
  set demoTitles to {{{items}}}
  set launcherId to {self._launcher_id if self._launcher_id else 0}
  set toClose to {{}}
  repeat with w in windows
    try
      set wid to id of w
      if wid is launcherId then
        -- skip launcher
      else
        set t to custom title of selected tab of w
        if t is in demoTitles then
          set end of toClose to w
        end if
      end if
    end try
  end repeat
  repeat with w in toClose
    try
      close w saving no
    end try
  end repeat
end tell
'''
        try:
            subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=20)
        except Exception as e:
            print(f"{C_WARN}  [Demo] 窓クローズの一部に失敗: {e}{C_RST}")

        # 念のため残存タイトルを再スキャン
        try:
            subprocess.run(["osascript", "-e", f'''
tell application "Terminal"
  set demoTitles to {{{items}}}
  repeat with w in windows
    try
      set t to custom title of selected tab of w
      if t is in demoTitles then
        close w saving no
      end if
    end try
  end repeat
end tell
'''], capture_output=True, text=True, timeout=15)
        except Exception:
            pass


class DemoCouncilHook:
    def __init__(self, stage: DemoStage):
        self.stage = stage

    def on_opinion(self, name, entropy, cloud_str):
        self.stage.write(name, f"H={entropy:.2f}  {cloud_str}")

    def on_transfer(self, src, dst, label="consensus"):
        self.stage.transfer(src, dst, label)

    def on_round(self, rnd):
        self.stage.broadcast(f"── Round {rnd} ──")

    def on_answer(self, text):
        self.stage.consensus_banner(text)

    def on_input_wait(self):
        self.stage.highlight_input(True)

    def on_input_done(self):
        self.stage.highlight_input(False)
