#!/usr/bin/env python3
"""
demo_board.py — デモ用・同一ウィンドウの役割タイル描画
==============================================================================
macOS で「書類をタブで開く=常に」のとき、複数 Terminal ウィンドウが作れない
環境向け。1つの大きなターミナルに役割グリッドを描く。
"""
from __future__ import annotations

import argparse
import os
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
HL = "\033[7m"
BOLD = "\033[1m"
DIM = "\033[90m"


def _term_size():
    try:
        import shutil
        sz = shutil.get_terminal_size((120, 40))
        return max(80, sz.columns), max(24, sz.lines)
    except Exception:
        return 120, 40


def _read_tail(path, n=8):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        return lines[-n:]
    except OSError:
        return []


def _cell(role, lines, width, height, highlight=False):
    color = ROLE_COLORS.get(role, "\033[97m")
    inner_w = max(10, width - 2)
    top = "┌" + f" {role} ".center(inner_w, "─")[:inner_w] + "┐"
    bot = "└" + "─" * inner_w + "┘"
    body_h = max(1, height - 2)
    rows = []
    if highlight:
        rows.append(HL + BOLD + color + top + RST)
    else:
        rows.append(color + top + RST)
    for i in range(body_h):
        raw = lines[i] if i < len(lines) else ""
        text = (raw[: inner_w - 1] + ("…" if len(raw) > inner_w - 1 else "")).ljust(inner_w)
        rows.append(f"{color}│{RST}{text}{color}│{RST}")
    rows.append(color + bot + RST)
    return rows


def _hstack(blocks):
    """同じ行数のセルを横に連結。"""
    if not blocks:
        return []
    h = len(blocks[0])
    out = []
    for r in range(h):
        out.append("".join(b[r] for b in blocks))
    return out


def render(roles, logs, highlight_file, result_log=None):
    cols_term, lines_term = _term_size()
    hl = bool(highlight_file and os.path.exists(highlight_file))
    # 上段: 役割 3列×2行、下段: INPUT (と RESULT があれば右)
    grid_roles = [r for r in roles if r not in ("INPUT", "RESULT")]
    n = len(grid_roles) or 1
    cols = min(3, n)
    rows_n = (n + cols - 1) // cols
    input_h = 6
    cell_w = max(24, (cols_term - 1) // cols)
    remain = max(12, lines_term - 2 - input_h - rows_n)
    cell_h = max(5, remain // max(1, rows_n))

    out = [DIM + " Verantyx Demo Board — 同一ウィンドウ・タイル表示 " + RST]
    idx = 0
    for _ in range(rows_n):
        row_roles = grid_roles[idx: idx + cols]
        idx += cols
        blocks = []
        for role in row_roles:
            path = logs.get(role, "")
            blocks.append(_cell(role, _read_tail(path, cell_h - 2), cell_w, cell_h,
                                highlight=False))
        while len(blocks) < cols:
            blocks.append(_cell("", [], cell_w, cell_h))
        out.extend(_hstack(blocks))

    in_path = logs.get("INPUT", "")
    res_path = result_log or logs.get("RESULT", "")
    if res_path and os.path.exists(res_path) and os.path.getsize(res_path) > 0:
        half = max(24, cols_term // 2)
        left = _cell("INPUT", _read_tail(in_path, input_h - 2), half, input_h, highlight=hl)
        right = _cell("RESULT", _read_tail(res_path, input_h - 2), cols_term - half, input_h)
        out.extend(_hstack([left, right]))
    else:
        out.extend(_cell("INPUT", _read_tail(in_path, input_h - 2),
                         cols_term - 2, input_h, highlight=hl))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="vx_demo_* ログディレクトリ")
    ap.add_argument("--roles", default="Commander,Scout-A,Scout-B,Worker-1,Worker-2,INPUT")
    ap.add_argument("--highlight-file", default="")
    a = ap.parse_args()
    roles = [x.strip() for x in a.roles.split(",") if x.strip()]
    logs = {r: os.path.join(a.dir, f"{r}.log") for r in roles}
    hl = a.highlight_file or os.path.join(a.dir, "INPUT.highlight")
    result_log = os.path.join(a.dir, "RESULT.log")
    sys.stdout.write("\033[?25l")  # hide cursor
    try:
        prev = ""
        while True:
            frame = render(roles, logs, hl, result_log)
            if frame != prev:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write(frame)
                sys.stdout.flush()
                prev = frame
            time.sleep(0.12)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n")


if __name__ == "__main__":
    main()
