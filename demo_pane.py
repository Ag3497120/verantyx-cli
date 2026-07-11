#!/usr/bin/env python3
"""
demo_pane.py — 映像壁の1セル / ドア転送アニメ対応
==============================================================================
layout.json で自分の画面座標と隣接を知る。
ログの @json 制御行でドア開閉・排出・注入・横断バナーを描画する。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

ROLE_COLORS = {
    "Commander": "\033[95m",
    "Scout-A": "\033[96m",
    "Scout-B": "\033[94m",
    "Worker-1": "\033[92m",
    "Worker-2": "\033[93m",
    "INPUT": "\033[97m",
    "RESULT": "\033[92m",
}
RST = "\033[0m"
DIM = "\033[90m"
BOLD = "\033[1m"
HL = "\033[7m"
YELLOW = "\033[93m"
CYAN = "\033[96m"


def term_size():
    try:
        sz = shutil.get_terminal_size((48, 16))
        return max(20, sz.columns), max(8, sz.lines)
    except Exception:
        return 48, 16


def clear():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def load_layout(path, role):
    if not path or not os.path.exists(path):
        return {}, {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pane = data.get("panes", {}).get(role, {})
        neighbors = data.get("neighbors", {}).get(role, {})
        return pane, neighbors
    except Exception:
        return {}, {}


def door_strip(side, width, height, open_=False, packet=""):
    """辺にドアを描くためのオーバーレイ行情報。"""
    # 返すのは描画時に使うメタ。実際の合成は render() 内。
    return {"side": side, "open": open_, "packet": packet,
            "width": width, "height": height}


def big_label(text, width):
    """役割名を大きく見せるための装飾行。"""
    t = text[: max(1, width - 4)]
    pad = max(0, width - 2 - len(t))
    left = pad // 2
    return " " * left + t + " " * (pad - left)


def render(role, title, lines, state, highlight=False):
    """
    state: {
      doors: {side: {open, packet}},
      flash: str|None,
      banner: str|None,
      vanish: {phase, text}|None,
    }
    """
    cols, rows = term_size()
    color = ROLE_COLORS.get(role, "\033[97m")
    doors = state.get("doors") or {}
    flash = state.get("flash")
    banner = state.get("banner")
    vanish = state.get("vanish")

    body_h = max(4, rows - 4)
    box_w = max(16, cols)

    # 永遠記憶への消滅表示
    if vanish:
        phase = int(vanish.get("phase") or 1)
        msg = vanish.get("text") or "永遠の記憶へ…"
        fade = "░" * min(box_w, 4 + phase * 6)
        out = [
            "\033[35m" + BOLD + "╔" + "═" * (box_w - 2) + "╗" + RST,
            "\033[35m" + BOLD + "║" + f" ETERNAL MEMORY ".center(box_w - 2)[: box_w - 2] + "║" + RST,
            "\033[35m║" + RST + big_label(role, box_w - 2)[: box_w - 2].ljust(box_w - 2) + "\033[35m║" + RST,
            "\033[35m║" + RST + big_label(msg, box_w - 2)[: box_w - 2].ljust(box_w - 2) + "\033[35m║" + RST,
            "\033[90m║" + fade.center(box_w - 2)[: box_w - 2] + "║" + RST,
            "\033[35m" + BOLD + "╚" + "═" * (box_w - 2) + "╝" + RST,
        ]
        return "\n".join(out)

    out = []
    # 上辺 (up ドア)
    up = doors.get("up")
    if up and up.get("open"):
        mid = f"══╗ {up.get('packet') or '↓'} ╔══"
        top = "═" * max(0, (box_w - len(mid)) // 2) + mid
        top = (top + "═" * box_w)[:box_w]
        out.append(YELLOW + BOLD + top + RST)
    else:
        top = "╔" + f" {title} ".center(box_w - 2, "═")[: box_w - 2] + "╗"
        if highlight:
            out.append(HL + BOLD + color + top[:box_w] + RST)
        else:
            out.append(color + top[:box_w] + RST)

    label = big_label(role.upper(), box_w - 2)
    hdr = "║" + label[: box_w - 2].ljust(box_w - 2) + "║"
    out.append(BOLD + color + hdr[:box_w] + RST)

    body_lines = list(lines[-(body_h - 1):])
    if banner:
        body_lines = [f"★ {banner}"] + body_lines
    if flash:
        body_lines = [flash] + body_lines
    while len(body_lines) < body_h - 1:
        body_lines.append("")

    left_d = doors.get("left")
    right_d = doors.get("right")
    door_row = max(1, (body_h - 1) // 2)

    for i, raw in enumerate(body_lines[: body_h - 1]):
        text = (raw[: box_w - 4] + ("…" if len(raw) > box_w - 4 else ""))
        text = text.ljust(box_w - 4)

        left_ch = "║"
        right_ch = "║"
        prefix = color
        suffix = color

        if i == door_row and left_d and left_d.get("open"):
            left_ch = "╣"
            pkt = left_d.get("packet") or "▶"
            text = (pkt + " " + text)[: box_w - 4].ljust(box_w - 4)
            prefix = YELLOW + BOLD
        if i == door_row and right_d and right_d.get("open"):
            right_ch = "╠"
            pkt = right_d.get("packet") or "▶"
            core = text.rstrip()
            room = box_w - 4 - len(pkt) - 1
            text = (core[: max(0, room)] + " " + pkt).ljust(box_w - 4)
            suffix = YELLOW + BOLD

        line = f"{prefix}{left_ch}{RST} {text} {suffix}{right_ch}{RST}"
        out.append(line[: box_w + 32])

    down = doors.get("down")
    if down and down.get("open"):
        mid = f"══╝ {down.get('packet') or '↑'} ╚══"
        bot = "═" * max(0, (box_w - len(mid)) // 2) + mid
        bot = (bot + "═" * box_w)[:box_w]
        out.append(YELLOW + BOLD + bot + RST)
    else:
        out.append(color + "╚" + "═" * (box_w - 2) + "╝" + RST)

    return "\n".join(out)


def apply_ctrl(state, obj):
    op = obj.get("op")
    if op == "door":
        side = obj.get("side", "right")
        doors = state.setdefault("doors", {})
        if obj.get("state") == "close":
            doors.pop(side, None)
        else:
            doors[side] = {
                "open": True,
                "packet": obj.get("packet") or "",
                "toward": obj.get("toward"),
            }
    elif op == "emit":
        side = obj.get("side", "right")
        doors = state.setdefault("doors", {})
        doors[side] = {
            "open": True,
            "packet": obj.get("packet") or "⟦data⟧",
            "toward": obj.get("toward"),
        }
        state["flash"] = f"▶ DOOR {side.upper()} OPEN → {obj.get('toward', '')}"
    elif op == "recv":
        side = obj.get("side", "left")
        doors = state.setdefault("doors", {})
        doors[side] = {
            "open": True,
            "packet": obj.get("packet") or "⟦data⟧",
            "toward": obj.get("fr"),
        }
        state["flash"] = f"▶ INJECT from {obj.get('fr', '')} via {side}"
    elif op == "banner":
        state["banner"] = obj.get("text", "")
    elif op == "vanish":
        state["vanish"] = {
            "phase": obj.get("phase", 1),
            "text": obj.get("text", "永遠の記憶へ…"),
        }
        state["doors"] = {}
        state["flash"] = None
    elif op == "clear":
        state["doors"] = {}
        state["flash"] = None
        state["banner"] = None
        state["vanish"] = None
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--layout", default="")
    ap.add_argument("--highlight-file", default="")
    a = ap.parse_args()
    title = a.title or a.role
    os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
    open(a.log, "a").close()

    pane, neighbors = load_layout(a.layout, a.role)
    state = {"doors": {}, "flash": None, "banner": None, "vanish": None}
    pos = 0
    buf = []
    if neighbors:
        buf.append(DIM + "neighbors: " + ", ".join(
            f"{k}={v}" for k, v in neighbors.items()) + RST)
    if pane.get("bounds"):
        b = pane["bounds"]
        buf.append(DIM + f"screen=[{b[0]:.0f},{b[1]:.0f}]-[{b[2]:.0f},{b[3]:.0f}]" + RST)

    clear()
    print(render(a.role, title, buf or ["(waiting…)"], state))

    try:
        while True:
            hl = bool(a.highlight_file and os.path.exists(a.highlight_file))
            changed = False
            try:
                size = os.path.getsize(a.log)
            except OSError:
                size = 0
            if size < pos:
                pos = 0
                buf = []
                changed = True
            if size > pos:
                with open(a.log, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                for line in chunk.splitlines():
                    if not line.strip():
                        continue
                    if line.startswith("@json "):
                        try:
                            obj = json.loads(line[6:])
                            apply_ctrl(state, obj)
                        except Exception:
                            buf.append(line)
                    else:
                        buf.append(line.rstrip())
                        # 通常ログが増えたら flash を薄める
                        if state.get("flash") and not line.startswith("@"):
                            pass
                changed = True

            # 常時再描画 (リサイズ・ハイライト・ドア状態)
            clear()
            print(render(a.role, title, buf, state, highlight=hl))
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
