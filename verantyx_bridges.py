"""
verantyx_bridges.py — 外部ローカルLLMサーバー連携 (Ollama / LM Studio)
==============================================================================
jgen や HF 直接ロード以外のモデルも評議会・エージェント・発話に参加させる。

交信できる情報のレベル (正直な整理):
  - jgen / HF 直ロード : 隠れ状態そのもの (ベクトル注入・強奪が可能)
  - LM Studio (OpenAI互換): logprobs -> 回答の「確率分布」まで取れる
    (第一トークンの top-k logprobs = 語彙分布インターリンガの近似)
  - Ollama : 生成テキストのみ (分布は取れないため、回答1点参加)

つまり外へ行くほど情報は粗くなるが、評議会の合意判定は語彙分布ベースなので
どのレベルの参加者も同じ土俵で議論に加われる。
"""

import json
import math
import re
import urllib.request

OLLAMA_URL = "http://localhost:11434"
LMSTUDIO_URL = "http://localhost:1234"


def _get(url, timeout=1.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(url, payload, timeout=180):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # urllib は本文を捨てるので、サーバーの実際のエラー理由を残す
        try:
            body = e.read().decode(errors="ignore")[:200]
        except Exception:
            body = ""
        raise RuntimeError(f"HTTP {e.code} {e.reason}"
                           + (f" — {body}" if body.strip() else "")) from None


def detect_backends():
    """稼働中のローカルLLMサーバーを検出して {name: [モデル,...]} を返す。"""
    found = {}
    try:
        tags = _get(f"{OLLAMA_URL}/api/tags")
        found["ollama"] = [m["name"] for m in tags.get("models", [])]
    except Exception:
        pass
    try:
        models = _get(f"{LMSTUDIO_URL}/v1/models")
        found["lmstudio"] = [m["id"] for m in models.get("data", [])]
    except Exception:
        pass
    return found


def _speak_system(concepts):
    """発話用の system prompt。思考を垂れ流させず結論を出させる。
    reasoning モデルは思考を止められないので、最後に必ず結論行を出させ、
    そこだけを _final_answer で抜き出す。"""
    sys_p = ("Answer concisely. If you must reason, keep it brief, then end your "
             "reply with a line starting exactly with 'Final answer:' followed by "
             "the complete conclusion in plain language.")
    if concepts:
        sys_p += " Council consensus concepts: " + ", ".join(concepts) + "."
    return sys_p


_THINK_TAGS = re.compile(r"(?is)<think>.*?</think>|<thinking>.*?</thinking>")
_THINK_LEAD = re.compile(
    r"(?is)^\s*(here'?s?\s+(a|my)\s+thinking\s+process.*?|let me think.*?|"
    r"okay,?\s+let'?s.*?|thinking\.\.\..*?)(?=\n\n|\Z)")


def _final_answer(text):
    """reasoning モデルの出力から思考部を落として結論だけを残す。
    <think> タグ・『Here's a thinking process』等の前置きを除去し、
    途切れた思考しか無い場合はそのまま返す (呼び出し側で polish される)。"""
    if not text:
        return text
    t = _THINK_TAGS.sub(" ", text).strip()
    # 明示の区切り (Final answer: / 結論: / 答え:) 以降を優先採用
    m = re.search(r"(?is)(?:final answer|final|結論|答え|回答)\s*[:：]\s*(.+)\Z", t)
    if m and len(m.group(1).strip()) > 1:
        return m.group(1).strip()
    # 思考の前置きだけを剥がす
    stripped = _THINK_LEAD.sub("", t).strip()
    return stripped or t


def _consensus_to_text(consensus_dist, top=6):
    """語彙分布インターリンガ -> テキスト表現 (API参加者用の劣化版注入)。
    隠れ状態を注入できない相手には、不確実性ごと言語化して渡す。"""
    if not consensus_dist:
        return ""
    items = ", ".join(f"{s.strip()} ({w*100:.0f}%)" for s, w in consensus_dist[:top] if s.strip())
    return f"\n[Council's current candidate distribution: {items}]"


class LMStudioParticipant:
    """LM Studio (OpenAI互換API) の評議会参加者。
    第一トークンの top_logprobs から回答分布を復元して参加する。"""

    def __init__(self, model=None):
        models = detect_backends().get("lmstudio", [])
        if not models:
            raise RuntimeError("LM Studio が localhost:1234 で見つかりません")
        self.model = model or models[0]
        self.name = f"lmstudio:{self.model.split('/')[-1][:24]}"

    @staticmethod
    def _content(choice):
        """通常モデルは content、reasoning モデルは reasoning_content に本文が入る。"""
        msg = choice["message"]
        return (msg.get("content") or "").strip(), (msg.get("reasoning_content") or "").strip()

    def opine_dist(self, question, consensus_dist=None):
        sys_p = ("Answer with only the single most likely answer word or token. "
                 "No explanation." + _consensus_to_text(consensus_dist))
        msgs = [{"role": "system", "content": sys_p},
                {"role": "user", "content": question}]
        r = _post(f"{LMSTUDIO_URL}/v1/chat/completions", {
            "model": self.model, "messages": msgs,
            "max_tokens": 4, "temperature": 0.0,
            "logprobs": True, "top_logprobs": 20,
        })
        choice = r["choices"][0]
        try:
            top = choice["logprobs"]["content"][0]["top_logprobs"]
            ws = [(t["token"], math.exp(t["logprob"])) for t in top]
            s = sum(w for _, w in ws) + 1e-12
            return [(t, w / s) for t, w in ws], ""
        except (KeyError, IndexError, TypeError):
            pass
        # logprobs 非対応 (MLX等) / reasoning モデル: 思考込みで再要求し回答1点参加
        content, inner = self._content(choice)
        if not content:
            r = _post(f"{LMSTUDIO_URL}/v1/chat/completions", {
                "model": self.model, "messages": msgs,
                "max_tokens": 1024, "temperature": 0.0,
            })
            content, inner = self._content(r["choices"][0])
        text = content or inner
        # 最後の意味のある語を回答とみなす ("The answer is Dave." -> "Dave")
        words = [w.strip(".,\"'()*:;!") for w in text.split()]
        words = [w for w in words if w]
        word = words[-1] if words else ""
        return ([(word, 1.0)] if word else []), inner

    def speak(self, question, concepts, max_new=80):
        sys_p = _speak_system(concepts)
        r = _post(f"{LMSTUDIO_URL}/v1/chat/completions", {
            "model": self.model,
            "messages": [{"role": "system", "content": sys_p},
                         {"role": "user", "content": question}],
            # reasoning モデル対策: effort=low で思考を短縮し (ornith-35b は
            # 放置すると結論前に数千トークン思考する)、予算も広めに確保
            "max_tokens": max(max_new, 2048), "temperature": 0.2,
            "reasoning_effort": "low",
        })
        choice = r["choices"][0]
        content, inner = self._content(choice)
        # 思考が予算を食い尽くして結論 (content) が空/断片のまま切れた場合:
        # 自身の思考の末尾を渡して「結論だけ」を二段目で強制取得する
        if choice.get("finish_reason") == "length" and len(content) < 40 and inner:
            r2 = _post(f"{LMSTUDIO_URL}/v1/chat/completions", {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content":
                     "(my reasoning so far)\n" + inner[-2000:]},
                    {"role": "user", "content":
                     "Time is up. Do not reason further. Based on your reasoning "
                     "above, state ONLY the complete final answer now, in the same "
                     "language as the question."},
                ],
                "max_tokens": 2048, "temperature": 0.2,
                "reasoning_effort": "low",
            })
            c2, i2 = self._content(r2["choices"][0])
            content = c2 or content or i2
        return _final_answer(content or inner)

    def _refresh_model(self):
        """LM Studio 側でモデルがアンロード/差し替えされた時に追従する。"""
        models = detect_backends().get("lmstudio", [])
        if models and self.model not in models:
            old = self.model
            self.model = models[0]
            self.name = f"lmstudio:{self.model.split('/')[-1][:24]}"
            return old
        return None

    def complete(self, messages, max_tokens=512):
        payload = {"model": self.model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": 0.1}
        try:
            r = _post(f"{LMSTUDIO_URL}/v1/chat/completions", payload)
        except RuntimeError as e:
            # 400 の典型: 参照モデルがもうロードされていない → 現行モデルで1回だけ再試行
            if "HTTP 400" not in str(e) or not self._refresh_model():
                raise
            payload["model"] = self.model
            r = _post(f"{LMSTUDIO_URL}/v1/chat/completions", payload)
        content, inner = self._content(r["choices"][0])
        return content or inner

    def close(self):
        pass


class OllamaParticipant:
    """Ollama の評議会参加者。分布は取れないため回答1点で参加する
    (合意判定は文字列レベルの第一候補比較なので、それでも投票に加われる)。"""

    def __init__(self, model=None):
        try:
            tags = _get(f"{OLLAMA_URL}/api/tags").get("models", [])
        except Exception:
            raise RuntimeError("Ollama が localhost:11434 で見つかりません")
        if not tags:
            raise RuntimeError("Ollama にモデルがありません")
        info = next((m for m in tags if m["name"] == model), tags[0] if model is None else None)
        if info is None:
            raise RuntimeError(f"Ollama にモデル '{model}' がありません")
        self.model = info["name"]
        # thinking対応モデルはデフォルト無効 (1応答に数分かかるため)。
        # allow_thinking=True で /think on による深い推論を許可。
        self.thinking = "thinking" in info.get("capabilities", [])
        self.allow_thinking = False
        self.name = f"ollama:{self.model.split(':')[0][:24]}"

    def _chat(self, messages, max_tokens):
        payload = {
            "model": self.model, "messages": messages, "stream": False,
            "options": {"temperature": 0.0, "num_predict": max_tokens},
        }
        if self.thinking:
            payload["think"] = self.allow_thinking
            if self.allow_thinking:
                payload["options"]["num_predict"] = max(max_tokens, 2048)
        r = _post(f"{OLLAMA_URL}/api/chat", payload, timeout=600)
        return r["message"]["content"].strip()

    def opine_dist(self, question, consensus_dist=None):
        sys_p = ("Answer with only the single most likely answer word or token. "
                 "No explanation." + _consensus_to_text(consensus_dist))
        text = self._chat([{"role": "system", "content": sys_p},
                           {"role": "user", "content": question}], 8)
        word = text.split()[0].strip(".,\"'") if text.split() else ""
        return ([(word, 1.0)] if word else []), ""

    def speak(self, question, concepts, max_new=80):
        sys_p = _speak_system(concepts)
        return _final_answer(self._chat([{"role": "system", "content": sys_p},
                                         {"role": "user", "content": question}],
                                        max(max_new, 1024)))

    def complete(self, messages, max_tokens=512):
        return self._chat(messages, max_tokens)

    def close(self):
        pass


def make_participant(spec):
    """'ollama' | 'ollama:model' | 'lmstudio' | 'lmstudio:model' から参加者を作る。"""
    kind, _, model = spec.partition(":")
    model = model or None
    if kind == "ollama":
        return OllamaParticipant(model)
    if kind == "lmstudio":
        return LMStudioParticipant(model)
    raise ValueError(f"unknown backend: {spec}")
