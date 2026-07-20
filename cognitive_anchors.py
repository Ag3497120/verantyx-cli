"""
cognitive_anchors.py — 認知アンカー (初期学習として常に持つ自己認識)
==============================================================================
ルーター/エージェントが生まれた瞬間から持っている「揺るがない前提」を定義する。
訓練による重み更新ではないが、常にプロンプトへ注入され、ルーティング判断の
土台になるため、実質的な初期学習 (inductive bias) として働く。

3つのアンカー:

  1. 時間アンカー (staleness anchor)
     システム時計と連動し「今日は YYYY-MM-DD。お前の重みの知識はそれより古い。
     時事・最新・価格・天気など時間に依存することは記憶で答えず web で調べよ」
     を常に自覚させる。知識のカットオフを過ぎた事柄への幻覚を防ぐ。

  2. ツール自己認識アンカー (tool-capability anchor)
     「お前には次のツールがあり、それらは自分の jgen につながっている。
     単体でも使えるが、組み合わせれば無限のことができる」を初期状態として持つ。
     ツールの存在自体を忘れて『できません』と答えるのを防ぐ。

  3. テレパシー・アンカー (cross-model gaze history)
     異種モデルの「いまどの Obsidian を見ているか／どの候補で考えているか」は
     中間グラフ履歴 (kind=telepathy) として共有される。相手の生ベクトルは読めないが、
     視線履歴を読めば相手の思考を推論できる、という前提を常に持つ。

これらは skill_memory の獲得スキルと違い、ユーザーに依らず不変の土台。
"""

import datetime
import os

# 重みの知識カットオフ (概算)。これより新しい事柄は web を要する自覚の基準。
KNOWLEDGE_CUTOFF = "2024-10"

# 時間依存の話題を示す語 (この語があれば記憶ではなく検索すべき自覚を強める)
TIME_SENSITIVE_HINTS = (
    "天気", "気温", "weather", "最新", "ニュース", "news", "株価", "為替", "レート",
    "価格", "いくら", "現在", "今の", "今日", "今週", "今年", "リアルタイム", "最近",
    "latest", "current", "today", "now", "recent", "price", "202",
)


def today_str():
    return datetime.date.today().isoformat()


def time_anchor(lang="ja"):
    """時計連動の知識陳腐アンカー。今日の日付を毎回埋め込む。"""
    today = today_str()
    if lang == "ja":
        return (f"【時間アンカー】今日は {today} です。あなたの重みに焼き込まれた知識は "
                f"{KNOWLEDGE_CUTOFF} 頃までのもので、それ以降は知りません。"
                "天気・ニュース・価格・最新情報・『今日/現在/最近』を含む問いは、"
                "記憶から答えず必ず web_search / fetch で今の事実を確認してください。"
                "古い知識を今の事実であるかのように答えてはいけません。")
    return (f"[TIME ANCHOR] Today is {today}. Your trained knowledge only goes up to "
            f"around {KNOWLEDGE_CUTOFF}; you do not know anything after that. "
            "For weather, news, prices, latest info, or anything with 'today/current/"
            "recent', do NOT answer from memory — verify current facts with web_search/"
            "fetch. Never present stale knowledge as if it were current.")


def is_time_sensitive(text):
    """この問いが時間依存 (記憶では危険、検索すべき) かを判定する。"""
    low = text.lower()
    return any(h in text or h in low for h in TIME_SENSITIVE_HINTS)


def tool_anchor(tool_specs=None, lang="ja"):
    """ツール自己認識アンカー。組み合わせで無限、という初期前提を植える。"""
    if lang == "ja":
        body = ("【ツールアンカー】あなたは単なるチャットではなく、手足 (ツール) を持つ"
                "エージェントです。これらのツールはあなたの jgen 本体に直結しています。"
                "1つでも使えますが、本質は『組み合わせ』です: 検索→取得→ファイル書込→"
                "シェル実行→アプリ操作を連鎖させれば、事実上あらゆるタスクを実現できます。"
                "『できません』の前に、どのツールをどう繋げば解けるかを必ず考えてください。")
    else:
        body = ("[TOOL ANCHOR] You are not a mere chatbot; you are an agent with hands "
                "(tools) wired directly into your jgen core. Each tool works alone, but "
                "your real power is COMBINATION: chaining search -> fetch -> write_file "
                "-> shell -> app-control lets you accomplish virtually any task. "
                "Before saying 'I can't', always work out which tools to chain.")
    if tool_specs:
        body += "\n" + tool_specs
    return body


def telepathy_anchor(lang="ja"):
    """異種モデル視線履歴 = 構造的テレパシーの認知アンカー。"""
    if lang == "ja":
        return (
            "【テレパシー・アンカー】他のモデルや役割の『生ベクトル』は直接読めません。"
            "代わりに、中間グラフ履歴 (kind=telepathy) に残された視線を読んでください:"
            "どの Obsidian ノートを見ているか、どの候補質量で考えているか、どの命題を主張しているか。"
            "それは相手の内部状態の圧縮であり、ベクトルに近い情報交換です。"
            "peer / SecondBrain / SpatialOverview に [Telepathy gaze|…] が出たら、"
            "相手の思考を推論する材料として必ず参照し、自分の視線も同じ形で残してください。"
        )
    return (
        "[TELEPATHY ANCHOR] You cannot read other models' raw vectors. "
        "Instead, read their gaze history on the mid-resolution graph (kind=telepathy): "
        "which Obsidian notes they are looking at, which candidate masses they hold, "
        "and which propositions they claim. That is compressed internal state — "
        "vector-like exchange across heterogeneous models. When you see "
        "[Telepathy gaze|…] in peer / SecondBrain slots, treat it as evidence of "
        "their thinking, and leave your own gaze in the same form."
    )


def full_preamble(tool_specs=None, lang="ja"):
    """エージェント system prompt の先頭に置く認知アンカー一式。"""
    return (time_anchor(lang) + "\n\n" + tool_anchor(tool_specs, lang)
            + "\n\n" + telepathy_anchor(lang))


# ── アンカーを「初期学習」として永遠の記憶に一度だけ刻む ──────────────────────
_SEEDED_FLAG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono", "anchors.seeded")


def seed_into_memory(council):
    """起動時に一度だけ、認知アンカーを記憶ノードとして刻印する。
    これにより反射弓 (RouterReflex) やペルソナが最初から土台を持つ。
    日付部分は毎起動で更新したいので、フラグは『概念の刻印済み』のみを管理する。"""
    if os.path.exists(_SEEDED_FLAG) or not getattr(council, "memory", None):
        return False
    if not council.memory.enabled:
        return False
    try:
        from verantyx_mind import embed_text
        seeds = [
            ("認知の土台: 私の知識は古く、時事・最新・天気・価格は web で調べる",
             ["時間", "検索", "最新", "知識の限界"]),
            ("認知の土台: 私はツールを持つエージェントで、組み合わせれば無限のことができる",
             ["ツール", "組み合わせ", "エージェント", "手足"]),
            ("認知の土台: 異種モデルの視線は中間グラフ履歴で共有され、相手の思考を推論できる",
             ["テレパシー", "視線", "Obsidian", "異種モデル", "telepathy"]),
        ]
        for text, concepts in seeds:
            v = embed_text(council.brain, council.tok, text)
            council.memory.add(v, text, concepts=concepts, kind="anchor")
        os.makedirs(os.path.dirname(_SEEDED_FLAG), exist_ok=True)
        open(_SEEDED_FLAG, "w").write(today_str())
        return True
    except Exception:
        return False


_TELEPATHY_SEEDED = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono", "anchors.telepathy")


def seed_telepathy_into_memory(council):
    """既存インストール向け: テレパシー・アンカーだけ追加刻印。"""
    if os.path.exists(_TELEPATHY_SEEDED) or not getattr(council, "memory", None):
        return False
    if not council.memory.enabled:
        return False
    try:
        from verantyx_mind import embed_text
        text = ("認知の土台: 異種モデルの視線は中間グラフ履歴で共有され、"
                "相手の思考を推論できる")
        v = embed_text(council.brain, council.tok, text)
        council.memory.add(
            v, text,
            concepts=["テレパシー", "視線", "Obsidian", "異種モデル", "telepathy"],
            kind="anchor",
        )
        os.makedirs(os.path.dirname(_TELEPATHY_SEEDED), exist_ok=True)
        open(_TELEPATHY_SEEDED, "w").write(today_str())
        return True
    except Exception:
        return False


if __name__ == "__main__":
    print(full_preamble("(tools here)"))
    print("\ntime-sensitive '今日の天気':", is_time_sensitive("今日の天気"))
    print("time-sensitive '空はなぜ青い':", is_time_sensitive("空はなぜ青い"))
