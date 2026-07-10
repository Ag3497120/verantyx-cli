"""
verantyx_browser.py — 実WebKitブラウザ (verantyx-browser --bridge) の Python ドライバ
==============================================================================
urllib のスクレイピングは User-Agent を詐称しても JS チャレンジ (Google Botguard,
Cloudflare) に弾かれ、202 や空応答になる。verantyx-ide の verantyx-browser は
OS ネイティブの WebKit (wry/WKWebView) で実ページをレンダリングするため、
ボットからは「本物のブラウザ」に見え、JS 実行後の DOM を取得できる。

プロトコル (stdin/stdout の JSON 行):
  → {"cmd":"navigate","url":"..."}         ページ遷移
  ← {"status":"hitl_done","markdown":"..."} DOM 沈静化 2秒後に自動発火 (JS描画後)
  → {"cmd":"get_page"}                       明示的に現在 DOM を要求
  ← {"status":"ok","markdown":"..."}
  → {"cmd":"quit"}

このドライバは検索エンジンの結果ページを実レンダリングして markdown で受け取り、
リンクとスニペットを抽出する。取れなければ urllib へフォールバックする。
"""

import json
import os
import re
import subprocess
import threading
import time
import urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
# ビルド済みバイナリの候補 (release 優先)
_BIN_CANDIDATES = [
    os.path.join(BASE, "cli/VerantyxIDE/verantyx-browser/target/release/verantyx-browser"),
    os.path.join(BASE, "cli/VerantyxIDE/verantyx-browser/target/debug/verantyx-browser"),
    os.path.join(BASE, "cli/VerantyxIDE/Resources/verantyx-browser"),
    os.path.join(BASE, "cortex/verantyx-browser/target/release/verantyx-browser"),
]


def find_binary():
    env = os.environ.get("VERANTYX_BROWSER_BIN")
    if env and os.path.exists(env):
        return env
    for p in _BIN_CANDIDATES:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None


class StealthBrowser:
    """verantyx-browser --bridge を1プロセス起動し、複数リクエストを捌く。
    GUI イベントループなので macOS のウィンドウサーバーが必要 (ヘッドレス不可)。"""

    def __init__(self, visible=False, boot_timeout=8.0):
        self.bin = find_binary()
        if self.bin is None:
            raise RuntimeError("verantyx-browser バイナリが見つかりません "
                               "(cargo build --release が必要)")
        args = [self.bin, "--bridge"]
        if visible:
            args.append("--visible")
        self.proc = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._lines = []
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()
        # PAGE_READY (初期空DOM描画完了) を待つ
        self._wait_status(("ok", "ready"), timeout=boot_timeout)

    def _pump(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            with self._lock:
                self._lines.append(obj)

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _wait_status(self, statuses, timeout=20.0, want_markdown=False):
        """指定 status のレスポンスが来るまで待つ。statuses は文字列 or タプル集合。"""
        if isinstance(statuses, str):
            statuses = (statuses,)
        t0 = time.time()
        idx = 0
        while time.time() - t0 < timeout:
            with self._lock:
                buf = self._lines[idx:]
                idx = len(self._lines)
            for obj in buf:
                if obj.get("status") in statuses:
                    if not want_markdown or obj.get("markdown"):
                        return obj
            if self.proc.poll() is not None:
                break
            time.sleep(0.1)
        return None

    def fetch_markdown(self, url, settle_timeout=12.0):
        """URL を実レンダリングし、JS 描画後の markdown を返す。"""
        with self._lock:
            self._lines.clear()
        self._send({"cmd": "navigate", "url": url})
        # DOM 沈静化で自動発火する hitl_done を優先的に待つ
        resp = self._wait_status("hitl_done", timeout=settle_timeout, want_markdown=True)
        if resp is None:
            # 自動発火しなければ明示取得
            self._send({"cmd": "get_page"})
            resp = self._wait_status(("ok", "hitl_done"), timeout=8.0, want_markdown=True)
        return resp.get("markdown", "") if resp else ""

    def close(self):
        try:
            self._send({"cmd": "quit"})
        except Exception:
            pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


# ── 検索結果の抽出 (markdown から) ────────────────────────────────────────────
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_SKIP_HOSTS = ("google.", "bing.", "duckduckgo.", "startpage.", "youtube.com/redirect",
               "microsoft.", "gstatic.", "w3.org", "schema.org")


def extract_results(markdown, k=6):
    """検索結果ページの markdown から (title, url) を抽出する。"""
    out, seen = [], set()
    for m in _MD_LINK.finditer(markdown):
        title, url = m.group(1).strip(), m.group(2).strip()
        host = urllib.parse.urlparse(url).netloc.lower()
        if any(s in host for s in _SKIP_HOSTS) or url in seen:
            continue
        if len(title) < 3 or title.lower() in ("image", "images", "video", "cached"):
            continue
        seen.add(url)
        out.append((title, url))
        if len(out) >= k:
            break
    return out


_singleton = None


def get_browser():
    """使い回しのシングルトン (プロセス起動コストを1回に)。"""
    global _singleton
    if _singleton is None:
        _singleton = StealthBrowser()
    return _singleton


# 実レンダリングで結果が綺麗に取れる順 (html/lite は軽量かつリンクが素直)
_SEARCH_ENGINES = [
    "https://html.duckduckgo.com/html/?q=",
    "https://lite.duckduckgo.com/lite/?q=",
    "https://www.bing.com/search?q=",
]


def search(query, k=6):
    """実ブラウザで検索し、結果テキストを返す。失敗時は '' を返す。"""
    br = get_browser()
    q = urllib.parse.quote_plus(query)
    for engine in _SEARCH_ENGINES:
        md = br.fetch_markdown(engine + q)
        results = extract_results(md, k=k)
        if results:
            return "\n".join(f"- {t}\n  {u}" for t, u in results)
    return ""


# スクリプト/広告/解析由来のトークン (html2md がエスケープしても残る目印)
_JS_TOKENS = re.compile(
    r"function\s*\(|=>|module\.exports|define\.amd|window\.|document\.|"
    r"googletag|pubads|gtag|dataLayer|adsbygoogle|setTargeting|\bvar\b|"
    r"addEventListener|Cookies|\.push\(|\.js['\"]?\)|typeof ")


def clean_markdown(md):
    """html2md 出力から <script>/広告由来のミニファイJS・コメント残骸を落とす。"""
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.DOTALL)
    md = re.sub(r"\\([*<>{}()!&|/=])", r"\1", md)  # html2md のエスケープを戻す
    kept = []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            kept.append(line)
            continue
        if _JS_TOKENS.search(s) or s.startswith("/*") or s.startswith("<!--"):
            continue
        # インライン設定 JSON ("key":"val","key2":... ) を捨てる
        if s.count('":"') + s.count("':'") + s.count('":') >= 3:
            continue
        # 記号だらけ or バックスラッシュ多用の行 (本文は文字が主) を捨てる
        symbols = sum(c in "{}();=!&|<>*/\\" for c in s)
        if len(s) > 24 and symbols > len(s) * 0.18:
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def fetch(url):
    """実ブラウザで1ページを開き、本文 markdown を返す (JS/設定JSON残骸を除去)。
    生 DOM は WKWebView の IPC ペイロード上限で欠けるため markdown 経路を使う。"""
    return clean_markdown(get_browser().fetch_markdown(url))


if __name__ == "__main__":
    import sys
    b = find_binary()
    print("binary:", b)
    if b and len(sys.argv) > 1:
        print(search(" ".join(sys.argv[1:])))
