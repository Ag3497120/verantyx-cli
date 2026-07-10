"""
verantyx_agent.py — エージェントの手足 (ツール実行・ファイル編集・ウェブ検索)
==============================================================================
評議会/Mind を「話すだけ」から「動ける」存在にする実行層。

構成:
  - 頭脳バックエンド: LM Studio / Ollama / HF Sage (Ornith) / jgenワーカー
    を選択可能。ツール呼び出しの信頼性が要るため大きめのモデルを推奨。
  - 手足 (ツール):
      web_search : DuckDuckGo 検索 (API キー不要)
      fetch      : URL の本文を取得
      read_file / write_file / edit_file : ファイル操作
      shell      : シェル実行 (デフォルトで実行前に y/N 確認)
      memory     : 永遠の記憶 (Cortex) の検索
  - 記憶: タスクと結果を Cortex に刻印 (--secret で無効)

プロトコルは厳密なテキスト形式 (JSONツールコール非対応モデルでも動く):
  THOUGHT: <考え>
  TOOL: <ツール名>
  ARGS: {"key": "value"}
または
  FINAL: <最終回答>
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

C_SYS = "\033[90m"
C_TOOL = "\033[93m"
C_OUT = "\033[96m"
C_FIN = "\033[92m"
C_RST = "\033[0m"

MAX_OBS = 2200  # ツール出力をプロンプトに入れる際の上限文字数


def _urlopen(req, timeout):
    """macOS Python の証明書欠如に耐える urlopen (certifi -> 非検証の順で降格)。"""
    import ssl
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except Exception as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl._create_unverified_context()
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


# ── ツール実装 ────────────────────────────────────────────────────────────────
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _clean_html(fragment):
    """タグ除去 + インラインCSS残骸 (.css-xxx{...}, @media{...}) を落とす。"""
    txt = re.sub(r"(?s)<style[^>]*>.*?</style>", " ", fragment)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"@media[^{]*\{[^}]*\}", " ", txt)
    txt = re.sub(r"[\.#][\w\-,:\.\s]*\{[^}]*\}", " ", txt)
    return re.sub(r"\s+", " ", html.unescape(txt)).strip()


def _search_startpage(q):
    req = urllib.request.Request(
        f"https://www.startpage.com/sp/search?query={q}",
        headers={"User-Agent": UA})
    with _urlopen(req, timeout=15) as r:
        page = r.read().decode("utf-8", "ignore")
    titles = []
    for m in re.finditer(r'<a\b[^>]*data-testid="gl-title-link"[^>]*>(.*?)</a>',
                         page, re.DOTALL):
        href = re.search(r'href="([^"]+)"', m.group(0))
        if href:
            titles.append((href.group(1), m.group(1)))
    snips = re.findall(
        r'<p[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</p>', page, re.DOTALL)
    results = []
    for i, (url, title) in enumerate(titles[:6]):
        entry = f"- {_clean_html(title)[:120]}\n  {url}"
        if i < len(snips):
            entry += "\n  " + _clean_html(snips[i])[:220]
        results.append(entry)
    return results


def _search_ddg(q):
    req = urllib.request.Request(
        f"https://html.duckduckgo.com/html/?q={q}",
        headers={"User-Agent": UA})
    with _urlopen(req, timeout=15) as r:
        page = r.read().decode("utf-8", "ignore")
    results = []
    for m in re.finditer(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page):
        url, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        um = re.search(r"uddg=([^&]+)", url)
        if um:
            url = urllib.parse.unquote(um.group(1))
        results.append(f"- {html.unescape(title).strip()}\n  {url}")
        if len(results) >= 6:
            break
    snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page)
    for i, s in enumerate(snips[:len(results)]):
        results[i] += "\n  " + html.unescape(re.sub(r"<[^>]+>", "", s)).strip()[:200]
    return results


def _stealth_search(query, k=6):
    """実WebKit (verantyx-browser) でJSチャレンジを越えて検索する。
    バイナリ不在・GUI不可の環境では例外を投げるので呼び出し側でフォールバック。"""
    import verantyx_browser
    return verantyx_browser.search(query, k=k)


def tool_web_search(args):
    query = args["query"]
    # 1) 実ブラウザ (ボットガード回避)。失敗したら urllib スクレイプへ降格
    try:
        got = _stealth_search(query)
        if got:
            return got
    except Exception:
        pass
    q = urllib.parse.quote_plus(query)
    results = []
    for engine in (_search_startpage, _search_ddg):
        try:
            results = engine(q)
        except Exception:
            results = []
        if results:
            break
    return "\n".join(results) if results else "(no results)"


def tool_fetch(args):
    url = args["url"]
    # 実ブラウザで JS 描画後の本文を取得。失敗時は素の HTTP へ降格
    try:
        import verantyx_browser
        md = verantyx_browser.fetch(url)
        if md and len(md) > 80:
            return md[:6000]
    except Exception:
        pass
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 VerantyxAgent/1.0"})
    with _urlopen(req, timeout=20) as r:
        page = r.read(600_000).decode("utf-8", "ignore")
    page = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    return re.sub(r"\s+", " ", text).strip()[:6000]


def tool_read_file(args):
    path = os.path.expanduser(args["path"])
    with open(path, "r", errors="replace") as f:
        content = f.read(60_000)
    start = int(args.get("start_line", 1))
    lines = content.splitlines()
    sel = lines[start - 1:start - 1 + int(args.get("num_lines", 200))]
    return "\n".join(f"{start+i:5d}| {l}" for i, l in enumerate(sel)) or "(empty)"


def tool_write_file(args):
    path = os.path.expanduser(args["path"])
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(args["content"])
    return f"wrote {len(args['content'])} chars to {path}"


def tool_edit_file(args):
    path = os.path.expanduser(args["path"])
    with open(path, "r") as f:
        src = f.read()
    old = args["old"]
    if old not in src:
        return "ERROR: old string not found in file (must match exactly)"
    if src.count(old) > 1:
        return f"ERROR: old string matches {src.count(old)} times; add more context"
    with open(path, "w") as f:
        f.write(src.replace(old, args["new"], 1))
    return f"edited {path}"


class Confirmer:
    """副作用のあるツールの実行前確認。auto_yes で一括スキップ可。"""

    def __init__(self, auto_yes=False):
        self.auto_yes = auto_yes

    def ask(self, tool, summary):
        if self.auto_yes:
            return True
        try:
            ans = input(f"{C_TOOL}  ⚠ {tool} を実行しますか? {summary} [y/N/a(以後すべて許可)] {C_RST}").strip().lower()
        except EOFError:
            return False
        if ans == "a":
            self.auto_yes = True
            return True
        return ans in ("y", "yes")


def _deny(tool):
    return f"USER DENIED execution of {tool}"


class ShellTool:
    def __init__(self, confirmer):
        self.confirmer = confirmer

    def __call__(self, args):
        cmd = args["command"]
        if not self.confirmer.ask("shell", f"`{cmd}`"):
            return _deny("shell")
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        out = (p.stdout + p.stderr).strip()
        return f"exit={p.returncode}\n{out}" if out else f"exit={p.returncode} (no output)"


class ConfirmedTool:
    """任意のツールを確認つきにするラッパー。"""

    def __init__(self, fn, name, confirmer, summarize=None):
        self.fn, self.name, self.confirmer = fn, name, confirmer
        self.summarize = summarize or (lambda a: str(a)[:100])

    def __call__(self, args):
        if not self.confirmer.ask(self.name, self.summarize(args)):
            return _deny(self.name)
        return self.fn(args)


# ── コンピュータ操作ツール (macOS) ────────────────────────────────────────────
def tool_open_app(args):
    import computer_control as cc
    return cc.open_app(args["name"])


def tool_ui_elements(args):
    import computer_control as cc
    items = cc.ui_elements(args.get("app"))
    if not items:
        return "(no UI elements found; アクセシビリティ権限を確認)"
    return "\n".join(f"- {e['role']} '{e['title']}' center={e['center']}" for e in items)


def tool_click(args):
    import computer_control as cc
    if "text" in args:
        return cc.click_text(args["text"])
    return cc.click(float(args["x"]), float(args["y"]),
                    double=bool(args.get("double", False)))


def tool_type_text(args):
    import computer_control as cc
    if "hotkey" in args:
        return cc.hotkey(args["hotkey"])
    return cc.type_text(args["text"])


def tool_screen_read(args):
    import computer_control as cc
    items = cc.screen_read(imprint=True, label=args.get("label", "agent screen_read"))
    if not items:
        return "(nothing recognized; 画面収録権限を確認)"
    return "\n".join(f"- '{t}' at ({x:.0f}, {y:.0f})" for t, x, y in items[:50])


class LexiconTool:
    """重み静的辞書。最大の jgen (Ornith 22GB) を発火させずに mmap 連想検索。"""

    def __init__(self):
        self._lex = None

    def __call__(self, args):
        if self._lex is None:
            from weight_lexicon import default_lexicon
            self._lex = default_lexicon()
        if "analogy" in args:  # {"analogy": ["man", "king", "woman"]}
            a, b, c = args["analogy"]
            pairs = self._lex.analogy(a, b, c)
            head = f"{a}:{b} = {c}:?"
        else:
            word = args["word"]
            pairs = self._lex.associate(word, k=int(args.get("k", 10)))
            head = f"associations of '{word}' in weight space"
        if not pairs:
            return "(no associations found)"
        return head + "\n" + "\n".join(f"- {t}  ({s:.3f})" for t, s in pairs)


class MemoryTool:
    """永遠の記憶の検索。初回使用時にルーター(0.5B)を遅延ロードする。"""

    def __init__(self):
        self._ctx = None

    def _load(self):
        if self._ctx is None:
            from transformers import AutoTokenizer
            from verantyx_mind import (DEFAULT_MODEL, TOKENIZER, AxisAnchors,
                                       CortexMemory, RustBrain, embed_text)
            tok = AutoTokenizer.from_pretrained(TOKENIZER)
            brain = RustBrain(DEFAULT_MODEL)
            mem = CortexMemory(AxisAnchors())
            self._ctx = (brain, tok, mem, embed_text)
        return self._ctx

    def __call__(self, args):
        brain, tok, mem, embed_text = self._load()
        qv = embed_text(brain, tok, args["query"])
        rows = mem.search(qv, k=int(args.get("k", 4)), query_text=args["query"])
        if not rows:
            return "(no memories found)"
        return "\n".join(f"- sim={sim:.2f} {text}" for text, sim, _, _, _ in rows)

    def imprint(self, task, answer):
        brain, tok, mem, embed_text = self._load()
        label = f"Task: {task}  →  Result: {answer[:140]}"
        mem.add(embed_text(brain, tok, label), label, kind="agent")

    def close(self):
        if self._ctx is not None:
            self._ctx[0].close()


TOOL_SPECS = """You have these tools:
- web_search  ARGS: {"query": "search terms"}
- fetch       ARGS: {"url": "https://..."}
- read_file   ARGS: {"path": "...", "start_line": 1, "num_lines": 200}
- write_file  ARGS: {"path": "...", "content": "..."}
- edit_file   ARGS: {"path": "...", "old": "exact text", "new": "replacement"}
- shell       ARGS: {"command": "ls -la"}
- memory      ARGS: {"query": "what to recall from eternal memory"}
- lexicon     ARGS: {"word": "Tokyo"} or {"analogy": ["man", "king", "woman"]}
  (searches a 9B model's raw weights as a static dictionary, no inference)
- open_app    ARGS: {"name": "Safari"}
- ui_elements ARGS: {} or {"app": "Safari"}   (accurate buttons + coordinates)
- screen_read ARGS: {}   (OCR everything on screen with coordinates)
- click       ARGS: {"x": 100, "y": 200} or {"text": "Save"} or {"x":.., "y":.., "double": true}
- type_text   ARGS: {"text": "hello"} or {"hotkey": "cmd+s"}

Respond in EXACTLY one of these two formats (nothing else):

THOUGHT: <one short sentence>
TOOL: <tool name>
ARGS: <single-line JSON object>

or, when you have the answer:

FINAL: <your answer to the user>"""


# ── 頭脳バックエンド ──────────────────────────────────────────────────────────
class SageBackend:
    """HF直ロード (Ornith 9B / MPS) の complete() 互換ラッパー。"""

    def __init__(self):
        from verantyx_council import HFSage
        self.sage = HFSage()
        self.name = self.sage.name

    def complete(self, messages, max_tokens=512):
        torch = self.sage.torch
        enc = self.sage.tok.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt").to("mps")
        with torch.no_grad():
            gen = self.sage.model.generate(
                enc, max_new_tokens=max_tokens, do_sample=False,
                pad_token_id=self.sage.tok.pad_token_id or self.sage.tok.eos_token_id)
        text = self.sage.tok.decode(gen[0][enc.shape[1]:], skip_special_tokens=True)
        # Ornith の Thinking Process 前置きを剥がす
        m = re.search(r"(?:THOUGHT:|TOOL:|FINAL:)", text)
        return text[m.start():] if m else text

    def close(self):
        self.sage.close()


def make_backend(spec):
    """'auto' | 'lmstudio[:model]' | 'ollama[:model]' | 'sage' -> complete() を持つ物体。
    auto は稼働中サーバーを 1 トークンの健全性チェックつきで順に試す。"""
    from verantyx_bridges import detect_backends, make_participant
    if spec != "auto":
        if spec == "sage":
            return SageBackend()
        return make_participant(spec)
    found = detect_backends()
    for cand in [k for k in ("lmstudio", "ollama") if k in found]:
        try:
            p = make_participant(cand)
            p.complete([{"role": "user", "content": "hi"}], max_tokens=4)
            print(f"{C_SYS}  [Agent] バックエンド自動選択: {p.name}{C_RST}")
            return p
        except Exception as e:
            print(f"{C_SYS}  [Agent] {cand} は応答不能 ({str(e)[:60]})。次を試します{C_RST}")
    print(f"{C_SYS}  [Agent] 外部サーバーなし。HF Sage (Ornith 9B) をロード{C_RST}")
    return SageBackend()


# ── エージェントループ ────────────────────────────────────────────────────────
PARSE_RE = re.compile(
    r"TOOL:\s*(\w+)\s*\n\s*ARGS:\s*(\{.*?\})\s*(?:\n|$)", re.DOTALL)


def parse_tool_call(out):
    """TOOL/ARGS ブロックを抽出する。ARGS は本物のJSONパーサ (raw_decode) で
    読むので、content 内の '}' やネストで壊れない。
    返り値: (name, args, args_error) — TOOL 自体が無ければ None。"""
    m = re.search(r"TOOL:\s*([\w-]+)\s*\n\s*ARGS:\s*", out)
    if m is None:
        return None
    name = m.group(1)
    rest = out[m.end():]
    i = rest.find("{")
    if i < 0:
        return (name, None, "ARGS missing JSON object")
    try:
        args, _ = json.JSONDecoder().raw_decode(rest[i:])
        return (name, args, None)
    except json.JSONDecodeError as e:
        return (name, None, f"invalid/truncated JSON ({e})")


def run_agent(task, backend, tools, max_steps=8, memory_tool=None, memorize=True,
              language=None, skill_hint=None, history=None):
    # 認知アンカー (時計連動の知識陳腐 + ツール自己認識) を初期学習として先頭に置く
    from cognitive_anchors import full_preamble
    anchor_lang = "en" if (language or "").lower().startswith("en") else "ja"
    sys_p = (full_preamble(TOOL_SPECS, lang=anchor_lang) + "\n\n"
             "You are Verantyx Agent, an autonomous assistant with tools. "
             "Work step by step. Use at most one tool per response. "
             "When calling a tool, output ONLY the THOUGHT/TOOL/ARGS lines — "
             "no plans, headings, or prose before them. "
             "Prefer FINAL as soon as you can answer.\n"
             "If the user refers to previous work ('さっきの', '以前の', 'that project'), "
             "you MUST locate the existing work first: check [SESSION HISTORY], the "
             "memory tool, and the filesystem (ls/read_file). NEVER invent or recreate "
             "a new project when asked to extend an existing one. If you cannot find "
             "it, ask the user for its location in FINAL instead of guessing.\n"
             + (f"Write the FINAL answer in {language}.\n" if language else ""))
    # 過去に学習した proven スキル (ツールの組み合わせ手順) があれば助言として注入
    if skill_hint:
        sys_p += (f"\n[LEARNED SKILL] For this kind of task you previously learned an "
                  f"efficient approach — follow it unless clearly wrong:\n{skill_hint}\n")
    # セッション履歴 (「さっきの」を解決する足場)。無ければ自動で永続ログから読む
    if history is None:
        try:
            from session_log import context_block
            history = context_block()
        except Exception:
            history = ""
    user_msg = task
    if history:
        user_msg = (f"[SESSION HISTORY] 直近のやり取り (参照解決に使う):\n{history}\n\n"
                    f"[CURRENT REQUEST]\n{task}")
    messages = [{"role": "system", "content": sys_p},
                {"role": "user", "content": user_msg}]
    final = None
    for step in range(1, max_steps + 1):
        # write_file 等の長い ARGS が途中で切れないよう広めに確保
        out = backend.complete(messages, max_tokens=2048).strip()
        fm = re.search(r"FINAL:\s*(.+)", out, re.DOTALL)
        tc = parse_tool_call(out)
        tool_pos = out.find("TOOL:")
        if tc is not None and (not fm or tool_pos < fm.start()):
            name, args, perr = tc
            thought = re.search(r"THOUGHT:\s*(.+)", out)
            if thought:
                print(f"{C_SYS}  💭 {thought.group(1).splitlines()[0][:100]}{C_RST}")
            if perr is not None:
                # ARGS が壊れている/途切れている → 垂れ流さず出し直させる
                obs = (f"ERROR: your ARGS for '{name}' was {perr}. Re-send ONLY "
                       "THOUGHT / TOOL / ARGS with complete JSON. If writing a large "
                       "file, split it into multiple smaller write_file calls.")
                print(f"{C_TOOL}  ✗ {name} 引数パース失敗 ({perr}) → 再送を要求{C_RST}")
            else:
                fn = tools.get(name)
                if fn is None:
                    obs = f"ERROR: unknown tool '{name}'"
                else:
                    print(f"{C_TOOL}  🔧 [{step}/{max_steps}] {name} "
                          f"{json.dumps(args, ensure_ascii=False)[:120]}{C_RST}")
                    try:
                        obs = str(fn(args))
                    except Exception as e:
                        obs = f"ERROR: {type(e).__name__}: {e}"
            if len(obs) > MAX_OBS:
                obs = obs[:MAX_OBS] + f"\n...(truncated, {len(obs)} chars total)"
            print(f"{C_OUT}{_indent(obs[:600])}{C_RST}")
            messages.append({"role": "assistant", "content": out})
            messages.append({"role": "user", "content": f"OBSERVATION:\n{obs}"})
            continue
        if fm:
            final = fm.group(1).strip()
        else:
            final = out  # フォーマット無視の回答もそのまま最終回答として扱う
        break
    if final is None:
        # ステップ上限: 観察を捨てず、ツール禁止でまとめの1ターンを強制する
        print(f"{C_SYS}  💭 ツール予算を使い切りました。観察結果から最終回答を合成します{C_RST}")
        messages.append({"role": "user", "content":
                         "Tool budget exhausted. Do NOT call any more tools. "
                         "Write 'FINAL:' now with your best answer, synthesizing "
                         "everything you observed so far."})
        for _ in range(2):
            out = backend.complete(messages, max_tokens=900).strip()
            fm = re.search(r"FINAL:\s*(.+)", out, re.DOTALL)
            if fm:
                final = fm.group(1).strip()
                break
            if "TOOL:" in out:
                # まだツールを呼ぼうとした → 拒否して言い直させる
                messages.append({"role": "assistant", "content": out})
                messages.append({"role": "user", "content":
                                 "OBSERVATION: ERROR: no more tool calls allowed. "
                                 "Respond with 'FINAL:' followed by your answer."})
                continue
            final = out.strip()
            break
        if not final:
            final = "(ステップ上限に達しました。ここまでの観察で答えられていません)"
    print(f"\n{C_FIN}  ✅ {final}{C_RST}")
    if memorize and memory_tool is not None:
        try:
            memory_tool.imprint(task, final)
            print(f"{C_SYS}  [Memory] タスクと結果を刻印しました{C_RST}")
        except Exception as e:
            print(f"{C_SYS}  [Memory] 刻印失敗: {e}{C_RST}")
    return final


def _indent(s, pad="     "):
    return "\n".join(pad + l for l in s.splitlines())


def build_tools(memory_tool, confirmer):
    """全ツールを組み立てる。副作用のあるものは確認つき。"""
    tools = {
        # 読み取り系 (確認なし)
        "web_search": tool_web_search,
        "fetch": tool_fetch,
        "read_file": tool_read_file,
        "memory": memory_tool,
        "lexicon": LexiconTool(),
        "ui_elements": tool_ui_elements,
        "screen_read": tool_screen_read,
        # 副作用系 (確認つき)
        "shell": ShellTool(confirmer),
        "write_file": ConfirmedTool(
            tool_write_file, "write_file", confirmer,
            lambda a: f"{a.get('path')} ({len(a.get('content', ''))} chars)"),
        "edit_file": ConfirmedTool(
            tool_edit_file, "edit_file", confirmer,
            lambda a: str(a.get('path'))),
        "open_app": ConfirmedTool(
            tool_open_app, "open_app", confirmer, lambda a: str(a.get('name'))),
        "click": ConfirmedTool(
            tool_click, "click", confirmer,
            lambda a: a.get('text') or f"({a.get('x')}, {a.get('y')})"),
        "type_text": ConfirmedTool(
            tool_type_text, "type_text", confirmer,
            lambda a: a.get('hotkey') or repr(a.get('text', ''))[:60]),
    }
    return tools


def main():
    ap = argparse.ArgumentParser(description="Verantyx Agent: ツール実行つきエージェント")
    ap.add_argument("--task", default=None, help="タスク (省略時は対話)")
    ap.add_argument("--backend", default="auto",
                    help="auto | lmstudio[:model] | ollama[:model] | sage")
    ap.add_argument("--max-steps", type=int, default=8)
    ap.add_argument("--yes", action="store_true", help="全ツールの実行確認を省略")
    ap.add_argument("--secret", action="store_true", help="記憶への刻印なし")
    args = ap.parse_args()

    print(f"{C_SYS}╔═══════════════════════════════════════════════╗")
    print(f"║  Verantyx Agent — 手足つき評議会               ║")
    print(f"╚═══════════════════════════════════════════════╝{C_RST}")
    backend = make_backend(args.backend)
    print(f"{C_SYS}  [Agent] 頭脳: {backend.name}{C_RST}")
    memory_tool = MemoryTool()
    tools = build_tools(memory_tool, Confirmer(auto_yes=args.yes))
    try:
        if args.task:
            run_agent(args.task, backend, tools, max_steps=args.max_steps,
                      memory_tool=memory_tool, memorize=not args.secret)
            return
        print(f"{C_SYS}  対話モード。'exit' で終了。{C_RST}")
        while True:
            try:
                task = input("\n🧑 Task: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not task or task.lower() in ("exit", "quit", "q"):
                break
            run_agent(task, backend, tools, max_steps=args.max_steps,
                      memory_tool=memory_tool, memorize=not args.secret)
    finally:
        backend.close()
        memory_tool.close()


if __name__ == "__main__":
    main()
