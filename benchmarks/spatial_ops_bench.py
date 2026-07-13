"""
spatial_ops_bench.py — Capture パッケージ向け Locate / Return / Relation 最小ベンチ
==============================================================================
実機 Export または benchmarks/datasets/capture_sample を読む。
Flat vs Graph vs JCross 比較はデータ蓄積後。ここでは登録集合内の健全性のみ。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spatial_episode import CapturePackage


def eval_package(pkg: CapturePackage, return_thresh_m: float = 0.05) -> dict:
    objs = pkg.objects()
    # Locate: displayName がある物は自分の名前で Top-1 が自分になるか
    locate_n = locate_hit = 0
    for o in objs:
        nm = o.get("displayName")
        if not nm:
            continue
        locate_n += 1
        hits = pkg.locate(nm)
        if hits and hits[0].get("objectID") == o.get("objectID"):
            locate_hit += 1

    # Return: poseHome を持つ object の位置誤差
    ret_n = ret_ok = 0
    errors = []
    for o in objs:
        oid = o.get("objectID")
        if not oid:
            continue
        r = pkg.return_error(oid)
        if r is None:
            continue
        ret_n += 1
        errors.append(r["positionErrorM"])
        if r["positionErrorM"] <= return_thresh_m:
            ret_ok += 1

    rels = pkg.relations()
    # Relation: containers.json（list or dict）の in が relations() に含まれるか
    expected = []
    raw = pkg.containers
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            parent = item.get("id") or item.get("containerID")
            for ch in item.get("childObjectIDs") or item.get("contents") or []:
                if isinstance(ch, str) and parent:
                    expected.append((parent, ch))
    elif isinstance(raw, dict):
        nested = raw.get("containers") if isinstance(raw.get("containers"), dict) else raw
        if isinstance(nested, dict):
            for parent, children in nested.items():
                if parent in ("containers", "relations", "version"):
                    continue
                if isinstance(children, list):
                    for ch in children:
                        cid = ch if isinstance(ch, str) else None
                        if cid:
                            expected.append((parent, cid))
    rel_n = len(expected)
    have = {(r.get("parent"), r.get("child")) for r in rels if r.get("type") == "in"}
    rel_hit = sum(1 for e in expected if e in have)

    drops = sum(1 for e in pkg.episodes if e.drop_flag)

    return {
        "objects": len(objs),
        "records": len(pkg.records),
        "episodes": len(pkg.episodes),
        "locate": {
            "n": locate_n,
            "hit": locate_hit,
            "accuracy": (locate_hit / locate_n) if locate_n else None,
        },
        "return": {
            "n": ret_n,
            "ok": ret_ok,
            "thresh_m": return_thresh_m,
            "accuracy": (ret_ok / ret_n) if ret_n else None,
            "median_error_m": float(sorted(errors)[len(errors)//2]) if errors else None,
        },
        "relation": {
            "n": rel_n,
            "hit": rel_hit,
            "accuracy": (rel_hit / rel_n) if rel_n else None,
            "edges_found": len(rels),
        },
        "drop_logs": drops,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--package",
        default=os.path.join(ROOT, "benchmarks/datasets/capture_sample"),
        help="Capture Export ルート",
    )
    ap.add_argument("--return-thresh-m", type=float, default=0.05)
    ap.add_argument("--out", default="", help="summary.json 出力先")
    a = ap.parse_args()

    pkg = CapturePackage(a.package)
    summary = eval_package(pkg, return_thresh_m=a.return_thresh_m)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    loc = summary["locate"]["accuracy"]
    ret = summary["return"]["accuracy"]
    rel = summary["relation"]["accuracy"]
    print(
        f"\n[spatial_ops] Locate={loc}  Return@{a.return_thresh_m}m={ret}  "
        f"Relation={rel}  drops={summary['drop_logs']}"
    )

    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
