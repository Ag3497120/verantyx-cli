#!/usr/bin/env python3
"""
demo_beam.py — ターミナル間を飛ぶデータパケット表示
==============================================================================
demo_stage がウィンドウ bounds を移動させ、このプロセスは中身だけ描く。
"""
from __future__ import annotations

import argparse
import os
import sys
import time

YELLOW = "\033[93m"
BOLD = "\033[1m"
RST = "\033[0m"
CYAN = "\033[96m"


def clear():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def frame(lines):
    pkt = lines[0] if lines else "⟦···⟧"
    route = lines[1] if len(lines) > 1 else ""
    art = [
        YELLOW + BOLD + "╔════════════════════╗" + RST,
        YELLOW + BOLD + "║  ✦ DATA IN FLIGHT  ║" + RST,
        YELLOW + "║" + RST + f"  {CYAN}{pkt[:16]:16s}{RST}  " + YELLOW + "║" + RST,
        YELLOW + "║" + RST + f"  {route[:16]:16s}  " + YELLOW + "║" + RST,
        YELLOW + BOLD + "╚════════════════════╝" + RST,
    ]
    return "\n".join(art)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    a = ap.parse_args()
    open(a.log, "a").close()
    pos = 0
    lines = ["⟦standby⟧", "parked"]
    clear()
    print(frame(lines))
    try:
        while True:
            try:
                size = os.path.getsize(a.log)
            except OSError:
                size = 0
            if size < pos:
                pos = 0
            if size > pos:
                with open(a.log, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                got = [ln for ln in chunk.splitlines() if ln.strip()]
                if got:
                    lines = got[-2:] if len(got) >= 2 else got + [""]
            clear()
            print(frame(lines))
            time.sleep(0.08)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
