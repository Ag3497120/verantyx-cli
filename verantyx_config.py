"""
verantyx_config.py — ロール別モデル割り当てと動作設定
=====================================================
これまでモデルの選択は「自動 (マシンのRAMとローカル資産をスキャンして評価)」
だけだったが、このモジュールで各ロールを明示的に固定できるようになる。

設定ファイル: リポジトリ直下の `verantyx.config.json`
(環境変数 VERANTYX_CONFIG でパスを上書き可)。存在しなければ全て "auto" で、
従来どおり model_scout / jgen_forge の自動評価が使われる。

ロールと指定できる値:
  models.router           ルーター(常駐 0.5B jgen)。 "auto" | .jgen のパス
  models.router_tokenizer ルーターのトークナイザ (HF repo id かローカルパス)
  models.worker           発話ワーカー。 "auto" | "none" | レジストリ名 | .jgen パス
  models.sage             大型賢者 (HF直ロード)。 "auto" | "none" | HFモデルdir/repo id
  models.lexicon          静的辞書。 "auto" | "none" | レジストリ名 | モデルパス
  models.agent_backend    エージェントの頭脳。 "auto" | "lmstudio[:model]" |
                          "ollama[:model]" | "sage"
  models.bridges          評議会に常時参加させる外部LLM。 "auto" (エスカレーション
                          時に自動招集) | [] | ["lmstudio:model", "ollama:model"]

動作設定:
  generation.speak_tokens "auto" | 整数 (発話トークン上限)
  generation.language     null | "日本語" | "English" など (発話言語の強制)
  escalation.enabled      true/false (自動エスカレーション)
  escalation.ram_fraction ワーカー自動選択に使うRAM割合 (既定 0.45)
  memory.enabled          永遠の記憶 (false で常時シークレット)

CLI からは Omni の /config コマンド、または
  python3 verantyx_config.py show
  python3 verantyx_config.py set models.worker qwen2.5-0.5b-worker
  python3 verantyx_config.py reset
"""
import copy
import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("VERANTYX_CONFIG",
                             os.path.join(_DIR, "verantyx.config.json"))

DEFAULTS = {
    "models": {
        "router": "auto",
        "router_tokenizer": "Qwen/Qwen1.5-0.5B-Chat",
        "worker": "auto",
        "sage": "auto",
        "lexicon": "auto",
        "agent_backend": "auto",
        "bridges": "auto",
    },
    "generation": {
        "speak_tokens": "auto",
        "language": None,
    },
    "escalation": {
        "enabled": True,
        "ram_fraction": 0.45,
        "bridge_timeout_s": 90,
    },
    "memory": {
        "enabled": True,
    },
}

_cache = None


def load(force=False):
    """設定を読み込む (DEFAULTS にファイルの内容を重ねる)。"""
    global _cache
    if _cache is not None and not force:
        return _cache
    cfg = copy.deepcopy(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                user = json.load(f)
            _deep_merge(cfg, user)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [Config] {CONFIG_PATH} の読み込みに失敗 ({e})。既定値で続行")
    _cache = cfg
    return cfg


def _deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def get(dotted, default=None):
    """get('models.worker') 形式で値を引く。"""
    node = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_value(dotted, value):
    """値を設定してファイルに保存する。'auto'/'none'/数値/JSONを解釈する。"""
    global _cache
    cfg = load()
    parts = dotted.split(".")
    node = cfg
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = _coerce(value)
    save(cfg)
    _cache = cfg
    return node[parts[-1]]


def _coerce(v):
    if not isinstance(v, str):
        return v
    low = v.lower()
    # "none" はモデル指定の有効値 (無効化) なので文字列のまま。null のみ None にする
    if low == "null":
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if v.lstrip("-").isdigit():
        return int(v)
    try:
        return float(v)
    except ValueError:
        pass
    try:
        return json.loads(v) if v[:1] in "[{" else v
    except json.JSONDecodeError:
        return v


def save(cfg=None):
    cfg = cfg or load()
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def reset():
    global _cache
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)
    _cache = None
    return load()


def describe():
    """/config 表示用: 現在値と既定値の差分を人間可読で返す。"""
    cfg = load()
    lines = []
    for section, kv in cfg.items():
        # skip comments / non-section scalars (e.g. top-level "_comment": "...")
        if not isinstance(kv, dict):
            continue
        for k, v in kv.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            dv = DEFAULTS.get(section, {}).get(k)
            mark = " *" if v != dv else ""
            lines.append(f"  {section}.{k} = {json.dumps(v, ensure_ascii=False)}{mark}")
    lines.append("  (* = 既定値から変更済み。verantyx.config.json に保存されます)")
    return "\n".join(lines)


# ── ロール解決ヘルパ (呼び出し側の分岐を1行にする) ──────────────────────────────
def resolve_router(fallbacks=()):
    """ルーター jgen のパスを返す。設定 > 環境変数 > 既存パス > レジストリ探索。"""
    v = get("models.router")
    if v and v != "auto" and os.path.exists(os.path.expanduser(v)):
        return os.path.expanduser(v)
    env = os.environ.get("JGEN_MODEL")
    if env and os.path.exists(env):
        return env
    for p in fallbacks:
        if p and os.path.exists(p):
            return p
    # レジストリから小さい ready ルーターを探す (Qwen2.5-0.5B=896 / 旧1024 など)
    try:
        import jgen_forge
        cands = [
            m for m in jgen_forge.load_registry()["models"]
            if m["status"] == "ready" and os.path.exists(m["jgen"])
            and (m.get("hidden") or 0) <= 1024
        ]
        if cands:
            # prefer smallest hidden (true 0.5B-class router), then smallest file
            cands.sort(key=lambda m: (m.get("hidden") or 10**9, m.get("size_bytes") or 0))
            return cands[0]["jgen"]
    except Exception:
        pass
    return None


def resolve_worker_pref():
    """発話ワーカーの指定。('auto'|'none'|名前|パス) をそのまま返す。"""
    return get("models.worker", "auto")


def resolve_sage_dir():
    """賢者のモデルディレクトリ。'auto' なら None (呼び出し側の既定を使う)。
    'none' なら False (賢者を使わない)。"""
    v = get("models.sage", "auto")
    if v == "none":
        return False
    if v and v != "auto":
        return os.path.expanduser(v)
    return None


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "show":
        print(f"config: {CONFIG_PATH}"
              f" ({'存在' if os.path.exists(CONFIG_PATH) else '未作成 (全て既定値)'})")
        print(describe())
    elif cmd == "set" and len(sys.argv) >= 4:
        val = set_value(sys.argv[2], " ".join(sys.argv[3:]))
        print(f"set {sys.argv[2]} = {json.dumps(val, ensure_ascii=False)}")
    elif cmd == "reset":
        reset()
        print("設定を既定値に戻しました")
    else:
        print("使い方: verantyx_config.py show | set <key> <value> | reset")
