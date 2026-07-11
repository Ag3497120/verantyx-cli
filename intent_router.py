"""
intent_router.py — 入口ルーティング (0.5B 認識 + 反射学習)
==============================================================================
Omni の最初の分岐「評議会 (chat) か エージェント (task) か」を、
キーワード辞書ではなくルーター自身に認識させる。

優先順位:
  1. 反射弓   — 過去に同種の依頼を正しく振った経験があれば即採用
  2. 明確動詞 — 編集/検索/ビルド等、誤爆しにくい語だけ即 task
  3. 時間アンカー — 時事は SEARCH (= task) へ
  4. 0.5B分類 — 次トークン分布で TASK / SEARCH / CHAT を採点 (自由生成しない)
  5. フォールバック — chat

学習の主体はベクトル介入可能なモデル (RustBrain) に限る。
外部 API モデルは分類にも学習にも使わない。
"""

from __future__ import annotations

import numpy as np

# 安全網: これがあればほぼ確実に作業。曖昧語 (アクセス/見て) は入れない。
_HARD_TASK = (
    "クローン", "clone", "インストール", "install", "ダウンロード", "download",
    "実行して", "走らせて", "ビルド", "build", "コンパイル", "compile",
    "コミット", "commit", "プッシュ", "push", "git ",
    "作成して", "作って", "書いて", "書き込んで", "編集して", "修正して",
    "削除して", "消して", "リネーム", "移動して", "コピーして",
    "create ", "write ", "edit ", "delete ", "remove ",
    "検索して", "調べて", "ググって", "search ", "look up", "fetch ",
    "開いて", "起動して", "クリック", "スクリーンショット", "スクショ",
    "open ", "launch ", "click ",
)

# ツール/外部操作の気配 (これがあれば事実質問補正をかけない)
_TOOLISH = (
    "アクセス", "閲覧", "参照", "読み取", "中身", "メモ", "notes", "アプリ",
    "ファイル", "フォルダ", "軌跡", "trace", "画面", "クリック", "シェル",
    "shell", "ツール", "tool", "開いて", "起動", "編集", "作成", "検索",
    "調べ", "実行", "ビルド", "clone", "git", "http", "www.", ".py", ".md",
    "fetch", "write", "read_file", "web",
)

# 知識で答えられる事実・議論の気配
_FACTOID = (
    "とは", "って何", "何ですか", "誰", "いつ", "どこ", "なぜ", "どうして",
    "直径", "首都", "化学式", "意味", "利点", "デメリット", "違い", "比較",
    "議論", "考えて", "説明して", "教えて",
    "what is", "what are", "who is", "why ", "how many", "explain", "discuss",
)

_LABEL_ALIASES = {
    "TASK": ("TASK", "Task", "task"),
    "SEARCH": ("SEARCH", "Search", "search"),
    "CHAT": ("CHAT", "Chat", "chat"),
}

_CLASSIFY_PROMPT = (
    "<|im_start|>system\n"
    "Intent router. Output exactly one of: TASK, SEARCH, CHAT.\n"
    "TASK = needs tools/files/apps/shell/Notes/local access\n"
    "SEARCH = needs live web info (weather, news, price, today)\n"
    "CHAT = knowledge or discussion only\n"
    "Examples:\n"
    "Q: edit README.md\nA: TASK\n"
    "Q: open Apple Notes and read it\nA: TASK\n"
    "Q: access the memo and view the trajectory\nA: TASK\n"
    "Q: what is the diameter of Mars?\nA: CHAT\n"
    "Q: ベクトル通信の利点を議論して\nA: CHAT\n"
    "Q: today's weather in Tokyo\nA: SEARCH\n"
    "<|im_end|>\n"
    "<|im_start|>user\n{text}<|im_end|>\n"
    "<|im_start|>assistant\n"
)


def hard_task_hint(text: str) -> bool:
    """明確な作業動詞があれば True。曖昧語は含めない。"""
    low = text.lower()
    return any(v in low or v in text for v in _HARD_TASK)


def soft_chat_hint(text: str) -> bool:
    """ツール気配がなく、事実/議論の問いなら True (0.5B の TASK 偏り補正用)。"""
    low = text.lower()
    if any(t in low or t in text for t in _TOOLISH):
        return False
    if any(f in low or f in text for f in _FACTOID):
        return True
    return text.rstrip().endswith(("?", "？"))


def _label_token_ids(tok):
    """各クラス → トークンIDリスト (1トークンで表せる表記のみ)。"""
    out = {}
    for label, aliases in _LABEL_ALIASES.items():
        ids = []
        for a in aliases:
            enc = tok.encode(a, add_special_tokens=False)
            if len(enc) == 1:
                ids.append(enc[0])
            enc2 = tok.encode(" " + a, add_special_tokens=False)
            if len(enc2) == 1:
                ids.append(enc2[0])
        out[label] = list(dict.fromkeys(ids))
    return out


def classify_with_router(brain, tok, text: str, dictionary) -> tuple[str, str]:
    """0.5B の次トークン分布で意図を採点する (自由生成しない)。
    戻り値: (intent, detail)  intent は 'task' | 'chat'
    SEARCH はエージェント (web) へ回すので task に正規化する。
    """
    if not getattr(brain, "vector_intervention", False):
        raise RuntimeError("intent classification requires a vector-intervention brain")
    prompt = _CLASSIFY_PROMPT.format(text=text[:800])
    ids = tok.encode(prompt, add_special_tokens=False)
    z = brain.encode(ids)
    logits = dictionary.logits(np.asarray(z, dtype=np.float32))
    label_ids = _label_token_ids(tok)
    scores = {}
    for label, tids in label_ids.items():
        if not tids:
            scores[label] = -1e9
            continue
        scores[label] = float(max(logits[t] for t in tids))
    vals = np.array([scores["TASK"], scores["SEARCH"], scores["CHAT"]], dtype=np.float64)
    vals -= vals.max()
    probs = np.exp(vals / 0.7)
    probs /= probs.sum()
    ranking = sorted(
        [("TASK", probs[0]), ("SEARCH", probs[1]), ("CHAT", probs[2])],
        key=lambda x: -x[1])
    best, p = ranking[0]
    detail = " ".join(f"{lab}={pr*100:.0f}%" for lab, pr in ranking)
    # 事実/議論なのに TASK/SEARCH 偏り → CHAT へ補正
    if best in ("TASK", "SEARCH") and soft_chat_hint(text):
        return "chat", detail + " (factoid→chat)"
    if best in ("TASK", "SEARCH"):
        return "task", detail
    if p < 0.45 and (probs[0] + probs[1]) >= p and not soft_chat_hint(text):
        return "task", detail + " (close→task)"
    return "chat", detail


def route(text: str, brain, tok, reflex=None, memory_enabled: bool = True,
          qvec=None, dictionary=None) -> dict:
    """入口ルーティングの本体。

    戻り値 dict:
      intent  : 'task' | 'chat'
      source  : 'reflex' | 'router' | 'hard' | 'anchor' | 'fallback'
      detail  : 人間向けの短い理由
      qvec    : 埋め込み (再利用用)
      raw     : 0.5B 採点の内訳
    """
    from verantyx_mind import embed_text
    import cognitive_anchors

    result = {"intent": "chat", "source": "fallback", "detail": "",
              "qvec": qvec, "raw": None}

    if result["qvec"] is None and getattr(brain, "vector_intervention", False):
        try:
            result["qvec"] = embed_text(brain, tok, text)
        except Exception as e:
            result["detail"] = f"embed failed: {e}"

    # 1) 反射弓
    if memory_enabled and reflex is not None and result["qvec"] is not None:
        adv = reflex.advise(result["qvec"])
        if adv and adv.get("intent") in ("task", "chat") and adv["sim"] >= 0.88:
            result["intent"] = adv["intent"]
            result["source"] = "reflex"
            result["detail"] = (f"類似経験 sim={adv['sim']:.2f} "
                                f"'{adv.get('src', '')}'")
            return result

    # 2) 明確な作業動詞
    if hard_task_hint(text):
        result["intent"] = "task"
        result["source"] = "hard"
        result["detail"] = "明確な作業動詞"
        return result

    # 3) 時間アンカー
    if cognitive_anchors.is_time_sensitive(text):
        result["intent"] = "task"
        result["source"] = "anchor"
        result["detail"] = "時間依存 → web 確認"
        return result

    # 4) 0.5B 次トークン採点
    if getattr(brain, "vector_intervention", False) and dictionary is not None:
        try:
            intent, raw = classify_with_router(brain, tok, text, dictionary)
            result["intent"] = intent
            result["source"] = "router"
            result["raw"] = raw
            result["detail"] = f"0.5B {raw}"
            return result
        except Exception as e:
            result["detail"] = f"router classify failed: {e}"

    result["intent"] = "chat"
    result["source"] = "fallback"
    if not result["detail"]:
        result["detail"] = "分類不能 → 評議会"
    return result


def learn_intent(reflex, brain, qvec, text: str, intent: str):
    """正しい振り分けを反射として刻印する (ベクトル介入モデルのみ)。"""
    if reflex is None or qvec is None:
        return None
    return reflex.record(qvec, text, intent=intent, brain=brain)


def looks_like_route_correction(text: str) -> str | None:
    """ユーザー発話が『ルートが違った』指摘なら、望む intent を返す。"""
    low = text.lower()
    wanted = any(w in text for w in ("ほしかっ", "欲しかっ", "すべき", "すべきだっ")) or \
             any(w in low for w in ("should have", "wanted you", "instead"))
    task_cues = (
        "検索", "調べ", "ツール", "エージェント", "手足", "アクセス", "開いて",
        "作業", "実行", "直接", "メモ", "notes",
        "search", "tool", "agent", "access", "open",
    )
    chat_cues = (
        "議論", "答えるだけ", "考えだけ", "ツールは不要", "検索しなくて",
        "エージェントは不要", "just answer", "no tools", "don't search", "discuss only",
    )
    if wanted and any(c in text or c in low for c in task_cues):
        return "task"
    if wanted and any(c in text or c in low for c in chat_cues):
        return "chat"
    if any(c in text or c in low for c in (
            "検索してほしかっ", "調べてほしかっ", "ツールを使", "手足を使",
            "アクセスしてほしかっ", "直接アクセス", "エージェントでやって",
            "should have searched", "should have used", "use the tool",
            "use the agent", "wanted you to search", "wanted you to access")):
        return "task"
    if any(c in text or c in low for c in (
            "議論してほしかっ", "答えるだけで", "考えだけで",
            "just answer", "no tools", "don't search", "discuss only")):
        return "chat"
    return None


if __name__ == "__main__":
    samples = [
        "appleのメモにアクセスして中身を見て",
        "火星の直径は？",
        "今日の東京の天気は？",
        "README.md を編集して",
        "前に直接アクセスしてくれたので軌跡を閲覧してほしい",
        "ベクトル通信の利点を議論して",
    ]
    print("hard hints only (no model):")
    for s in samples:
        print(f"  {'task' if hard_task_hint(s) else 'chat?':5} | {s[:50]}")
