"""
intent_router.py — 入口ルーティング (0.5B 認識 + 反射学習)
==============================================================================
Omni の最初の分岐「評議会 (chat) か エージェント (task) か」を、
キーワード辞書ではなくルーター自身に認識させる。

Phase 1 以降の本体は router_classifier.classify (分類専用・generate 禁止)。
このモジュールは後方互換の facade + キーワード安全網 + 学習ヘルパを残す。

優先順位 (router_classifier に委譲):
  1. 反射弓   — 過去に同種の依頼を正しく振った経験があれば即採用
  2. 明確動詞 — 編集/検索/ビルド等、誤爆しにくい語だけ即 task
  3. 時間アンカー — 時事は SEARCH
  4. 0.5B分類 — 次トークン分布 + AxisAnchors prior (自由生成しない)
  5. フォールバック — chat + ambiguous

学習の主体はベクトル介入可能なモデル (RustBrain) に限る。
外部 API モデルは分類にも学習にも使わない。

警告: Council / Matryoshka は別エントリポイントを使うこと。
分類経路に渡す脳は ClassifyOnlyBrain でラップされ generate() 不可。
"""

from __future__ import annotations

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
    """後方互換: 0.5B 次トークン採点 → ('task'|'chat', detail)。

    新規コードは router_classifier.classify を使うこと。
    SEARCH はエージェントへ回すので task に正規化する。
    """
    from router_classifier import wrap_for_classify, neuro_next_token_scores
    from router_classifier import _apply_soft_chat_correction

    clf = wrap_for_classify(brain)
    probs, detail = neuro_next_token_scores(clf, tok, text, dictionary)
    best, _ = max(probs.items(), key=lambda x: x[1])
    best, detail = _apply_soft_chat_correction(best, text, detail)
    if best in ("TASK", "SEARCH"):
        # close→task は classify() 本体側。ここは単純正規化
        p = probs[best]
        if p < 0.45 and (probs["TASK"] + probs["SEARCH"]) >= p and not soft_chat_hint(text):
            return "task", detail + " (close→task)"
        return "task", detail
    return "chat", detail


def route(text: str, brain, tok, reflex=None, memory_enabled: bool = True,
          qvec=None, dictionary=None, axes=None) -> dict:
    """入口ルーティングの本体 (classifier 委譲)。

    戻り値 dict:
      intent      : 'task' | 'chat'  (search は task に正規化)
      source      : 'reflex' | 'hard' | 'anchor' | 'neuro' | 'neuro+axis' | 'fallback'
      detail      : 人間向けの短い理由
      qvec        : 埋め込み (再利用用)
      raw         : 0.5B 採点の内訳
      label       : 'chat' | 'task' | 'search' (正規化前)
      confidence  : float
      scores      : dict
      ambiguous   : bool
      axis_sig    : optional
    """
    from router_classifier import classify

    # axes 未指定なら AxisAnchors があれば載せる (失敗しても分類は続行)
    if axes is None:
        try:
            from verantyx_mind import AxisAnchors
            axes = AxisAnchors()
            if not axes.available:
                axes = None
        except Exception:
            axes = None

    result = classify(
        text, brain, tok, dictionary,
        reflex=reflex, memory_enabled=memory_enabled, qvec=qvec, axes=axes)
    return result.as_route_dict()


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
    print("\nFull classify smoke: python scripts/smoke_router_classify.py")
