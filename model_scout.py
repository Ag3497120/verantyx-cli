"""
model_scout.py — ローカルモデルの自動探索と自律的な役割割り当て
==============================================================================
マシン上に存在するすべてのモデル資産を探索し、それぞれに最適な使い道を
自律的に割り当てる:

  役割:
    router   : jgen 0.5B (思考・記憶・ルーティングの核)
    worker   : jgen 変換済みモデル (ベクトル注入可能な評議会参加者/発話役)
    convert  : jgen 未変換だが対応アーキテクチャ (jgen_forge で変換可能)
    bridge   : Ollama / LM Studio がホストするモデル (API参加者)
    lexicon  : 静的辞書ソース (発火させずに mmap 検索。アーキテクチャ非対応や
               RAM に載らない巨大モデルでも、埋め込み/MLP が読めれば使える)

  探索場所:
    - jgen レジストリ (変換済み)
    - Ollama API / LM Studio API (稼働中サーバー)
    - HF キャッシュ (~/.cache/huggingface/hub)
    - local_weights / models_dropzone / ~/.lmstudio/models (safetensors, GGUF)
"""

import glob
import json
import os

HF_CACHE = os.path.expanduser("~/.cache/huggingface/hub")
BASE = os.path.dirname(os.path.abspath(__file__))
SEARCH_DIRS = [
    os.path.join(BASE, "local_weights"),
    os.path.join(BASE, "models_dropzone"),
    os.path.expanduser("~/.lmstudio/models"),
    os.path.expanduser("~/.cache/lm-studio/models"),
]


def _dir_size_gb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 2**30


def _snapshot_dir(hf_model_dir):
    """models--org--name 形式のキャッシュから実体 snapshot を探す。"""
    snaps = glob.glob(os.path.join(hf_model_dir, "snapshots", "*"))
    for s in sorted(snaps, reverse=True):
        if (glob.glob(os.path.join(s, "*.safetensors")) or
                os.path.exists(os.path.join(s, "model.safetensors.index.json"))):
            return s
    return None


def _arch_of(snap):
    try:
        cfg = json.load(open(os.path.join(snap, "config.json")))
        return cfg.get("architectures", ["?"])[0]
    except Exception:
        return "?"


def _has_tokenizer(snap):
    return any(os.path.exists(os.path.join(snap, f))
               for f in ("tokenizer.json", "tokenizer_config.json"))


def scan():
    """全資産を探索して [{name, kind, path, size_gb, roles, note}, ...] を返す。"""
    assets = []
    seen_paths = set()

    # 1. jgen レジストリ (変換済み = worker/router)
    try:
        import jgen_forge
        for m in jgen_forge.load_registry()["models"]:
            if not os.path.exists(m["jgen"]):
                continue
            roles = ["worker"] if m.get("status") == "ready" else []
            if "router" in m["name"]:
                roles = ["router"] + roles
            roles.append("lexicon")  # jgen は常に辞書にもなれる
            assets.append({
                "name": m["name"], "kind": "jgen", "path": m["jgen"],
                "tokenizer": m.get("tokenizer"),
                "size_gb": m["size_bytes"] / 2**30, "roles": roles,
                "note": m.get("status", ""),
            })
            seen_paths.add(os.path.realpath(m["jgen"]))
    except Exception:
        pass

    # 2. 稼働中サーバー (bridge)
    try:
        from verantyx_bridges import detect_backends
        for kind, models in detect_backends().items():
            for m in models:
                if "embed" in m:
                    continue
                assets.append({"name": f"{kind}:{m}", "kind": kind, "path": None,
                               "tokenizer": None, "size_gb": 0.0,
                               "roles": ["bridge"], "note": "稼働中サーバー"})
    except Exception:
        pass

    # 3. HF スナップショット (convert / lexicon)
    try:
        import jgen_forge
        standard = jgen_forge.STANDARD_ARCHS
    except Exception:
        standard = set()
    hf_dirs = []
    if os.path.isdir(HF_CACHE):
        hf_dirs += [os.path.join(HF_CACHE, d) for d in os.listdir(HF_CACHE)
                    if d.startswith("models--")]
    for base in SEARCH_DIRS:
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if d.startswith("models--"):
                    hf_dirs.append(p)
                elif os.path.isdir(p) and glob.glob(os.path.join(p, "**/*.safetensors"),
                                                    recursive=True):
                    hf_dirs.append(p)

    seen_names = {a["name"] for a in assets}
    for d in hf_dirs:
        snap = _snapshot_dir(d) if os.path.isdir(os.path.join(d, "snapshots")) else d
        if snap is None or os.path.realpath(snap) in seen_paths:
            continue
        seen_paths.add(os.path.realpath(snap))
        name = os.path.basename(d).replace("models--", "").replace("--", "/")
        if name in seen_names:
            continue
        seen_names.add(name)
        arch = _arch_of(snap)
        size = _dir_size_gb(snap)
        roles, note = [], arch
        if arch in standard:
            roles.append("convert")
            note += " (jgen変換可)"
        if _has_tokenizer(snap):
            roles.append("lexicon")
        if not roles:
            note += " (tokenizerなし)"
        assets.append({"name": name, "kind": "safetensors", "path": snap,
                       "tokenizer": snap if _has_tokenizer(snap) else None,
                       "size_gb": size, "roles": roles, "note": note})

    # 4. GGUF (LM Studio / Ollama の隠しフォルダ含む) — convert 候補
    try:
        import jgen_forge
        for s in jgen_forge.discover_sources():
            if s["source"] == "hf-cache":
                continue  # part 3 で処理済み
            rp = os.path.realpath(s["path"])
            if rp in seen_paths or s["name"] in seen_names:
                continue
            seen_paths.add(rp)
            seen_names.add(s["name"])
            assets.append({"name": s["name"], "kind": f"gguf/{s['source']}",
                           "path": s["path"], "tokenizer": None,
                           "size_gb": s["size_bytes"] / 2**30, "roles": ["convert"],
                           "note": f"{s['source']} (jgen_forge pull で変換可)"})
    except Exception:
        pass
    return assets


def best_lexicon_source():
    """静的辞書に最適なソースを自律選択する。
    知識の書き込み量はパラメータ数に比例するため『最大の lexicon 対応モデル』
    を選ぶ。safetensors は MLP probe も可能なので同サイズなら jgen より優先。"""
    cands = [a for a in scan() if "lexicon" in a["roles"] and a["tokenizer"]]
    if not cands:
        return None
    cands.sort(key=lambda a: (a["size_gb"], a["kind"] == "safetensors"), reverse=True)
    return cands[0]


def report(assets=None):
    """探索結果の整形テキスト。"""
    assets = assets or scan()
    lines = []
    order = {"router": 0, "worker": 1, "bridge": 2, "convert": 3, "lexicon": 4}
    for a in sorted(assets, key=lambda x: min(order.get(r, 9) for r in x["roles"]) if x["roles"] else 9):
        roles = ",".join(a["roles"]) or "未割当"
        size = f"{a['size_gb']:.1f}GB" if a["size_gb"] else "-"
        lines.append(f"  {a['name'][:44]:44s} {size:>8s}  [{roles}]  {a['note'][:36]}")
    best = best_lexicon_source()
    if best:
        lines.append(f"  → 静的辞書の自律選択: {best['name']} ({best['size_gb']:.1f}GB, {best['kind']})")
    return "\n".join(lines)


if __name__ == "__main__":
    print("── Model Scout: ローカルモデル探索 ──")
    print(report())
