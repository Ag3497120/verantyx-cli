#!/usr/bin/env python3
"""
verantyx.py — 対話式ランチャー (コマンド引数なしで全部ここから選ぶ)
==============================================================================
    python3 verantyx.py

起動するとモード選択メニューが出る:
  1. Omni              : 全機能内包 (議論/エージェント/辞書/視覚/記憶)。/help 参照
  2. Demo              : 評議会可視化 (複数ターミナル・使い勝手低下・要 yes 承認)
  3. Mind チャット     : 可視化つきベクトル思考 + 永遠の記憶 (0.5Bルーター)
  4. エージェント      : web検索/ファイル編集/アプリ操作の手足つき
  5. 静的辞書          : 9B重みを発火させずに mmap 連想検索
  6. 思考の軌跡        : 過去の議論を一覧・再生
  7. 記憶              : 検索 / ペルソナ / 統計

Omni 内スラッシュコマンドの全容は /help で表示。主要なもの:
  /model         発話役・参加モデルの選択 (jgen / Ollama / LM Studio / 9B)
  /lang X        応答言語の強制 (ja / en / ...)
  /think on|off  外部モデルの thinking (深い推論) 切替
  /secret        記憶バイアスの一時遮断を切替 (途中から再開可)
  /agent TASK    ツール実行 (web/ファイル/シェル/アプリ操作、確認つき)
  /screen /see   画面の視覚層刻印 (立体十字式圧縮) と検索
  /mem           RAM 使用状況とロード済みモデル (OOMガード)
"""

import os
import sys

C_SYS = "\033[90m"
C_TITLE = "\033[95m"
C_OPT = "\033[96m"
C_WARN = "\033[93m"
C_MEM = "\033[35m"
C_FIN = "\033[92m"
C_RST = "\033[0m"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)


def banner():
    print(f"{C_TITLE}")
    print("╔══════════════════════════════════════════════════════╗")
    print("║   V E R A N T Y X  —  Latent Cognition Suite          ║")
    print("║   立体十字構造体 / ベクトル評議会 / 永遠の記憶        ║")
    print(f"╚══════════════════════════════════════════════════════╝{C_RST}")


def choose(title, options, default=1):
    """番号選択。空 Enter でデフォルト。"""
    print(f"\n{C_TITLE}◆ {title}{C_RST}")
    for i, (label, desc) in enumerate(options, 1):
        mark = "*" if i == default else " "
        print(f"{C_OPT} {mark}{i}. {label:14s}{C_RST}{C_SYS} {desc}{C_RST}")
    while True:
        try:
            raw = input(f"  選択 [1-{len(options)}] (Enter={default}): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return None
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        if raw.lower() in ("q", "quit", "exit"):
            return None


def yesno(prompt, default=False):
    d = "y/N" if not default else "Y/n"
    try:
        raw = input(f"  {prompt} [{d}]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return default
    if not raw:
        return default
    return raw in ("y", "yes")


def ask_text(prompt, default=""):
    try:
        raw = input(f"  {prompt}{f' (Enter={default})' if default else ''}: ").strip()
    except (KeyboardInterrupt, EOFError):
        return default
    return raw or default


def detect_environment():
    """稼働中の外部LLMと登録済みjgenを表示。"""
    lines = []
    try:
        from verantyx_bridges import detect_backends
        for kind, models in detect_backends().items():
            lines.append(f"{kind}: {', '.join(models[:3])}")
    except Exception:
        pass
    try:
        import jgen_forge
        ready = [m["name"] for m in jgen_forge.load_registry()["models"]
                 if m.get("status") == "ready"]
        if ready:
            lines.append(f"jgen: {', '.join(ready[:4])}")
    except Exception:
        pass
    if lines:
        print(f"{C_SYS}  検出: " + "  |  ".join(lines) + C_RST)


# ── 1. Mind チャット ─────────────────────────────────────────────────────────
def launch_mind():
    steps = ask_text("思考ステップ (auto/数値)", "auto")
    worker = ask_text("発話ワーカー (auto/none/レジストリ名)", "auto")
    secret = yesno("シークレットモードで開始? (記憶を使わない)")
    import verantyx_mind
    sys.argv = ["verantyx_mind.py", "--steps", steps, "--worker", worker]
    if secret:
        sys.argv.append("--secret")
    verantyx_mind.main()


# ── 意図ルーティング (Omni: 議論か作業か) ─────────────────────────────────────
# Phase 1: 本番入口は router_classifier.classify (generate 禁止)。
# intent_router.route はその facade。Omni ログは confidence / ambiguous を明示。
def classify_intent(text):
    """モデルなしの安全網。本番の入口は intent_router.route / router_classifier.classify。"""
    from intent_router import hard_task_hint
    return "task" if hard_task_hint(text) else "chat"


# ── モデル選択 (Omni /model 用) ───────────────────────────────────────────────
def _list_speakers():
    """発話役/参加者に指定できる全モデルを列挙する。"""
    choices = [("router", "jgen 0.5B ルーター (最速)")]
    try:
        import jgen_forge
        for m in jgen_forge.load_registry()["models"]:
            if m.get("status") == "ready":
                choices.append((f"jgen:{m['name']}", f"jgen {m['name']}"))
    except Exception:
        pass
    try:
        from verantyx_bridges import detect_backends
        found = detect_backends()
        for m in found.get("ollama", []):
            choices.append((f"ollama:{m}", f"Ollama {m}"))
        for m in found.get("lmstudio", []):
            if "embed" not in m:
                choices.append((f"lmstudio:{m}", f"LM Studio {m}"))
    except Exception:
        pass
    choices.append(("sage", "HF直ロード Ornith 9B (要RAM ~19GB)"))
    return choices


def _make_speaker(spec, council):
    """spec からspeakerオブジェクトを作る。RAMガードつき。"""
    from memory_guard import GUARD
    if spec == "router":
        council._forced_speaker = None
        return "router (強制解除)"
    if spec == "sage":
        if not GUARD.ensure("hf_sage_9b", "Ornith 9B"):
            return None
        council._escalate(2, reason=" /model指定")
        council._forced_speaker = (council._sage.name, council._sage)
        return council._sage.name
    if spec.startswith("jgen:"):
        if not GUARD.can_load("jgen_worker", spec):
            return None
        import jgen_forge
        from verantyx_council import JGenParticipant
        name = spec.split(":", 1)[1]
        m = next((x for x in jgen_forge.load_registry()["models"] if x["name"] == name), None)
        if m is None:
            return None
        p = JGenParticipant(m)
        council._forced_speaker = (p.name, p)
        return p.name
    from verantyx_bridges import make_participant
    p = make_participant(spec)
    council._forced_speaker = (p.name, p)
    return p.name


def _add_council_member(spec, council):
    """spec のモデルを議論参加者 (opine_dist を持つ) として評議会に加える。"""
    from memory_guard import GUARD
    if spec == "sage":
        if not GUARD.ensure("hf_sage_9b", "Ornith 9B"):
            return None
        council._escalate(2, reason=" /council指定")
        return council._sage.name if council._sage else None
    if spec.startswith("jgen:"):
        if not GUARD.can_load("jgen_worker", spec):
            return None
        import jgen_forge
        from verantyx_council import JGenParticipant
        name = spec.split(":", 1)[1]
        m = next((x for x in jgen_forge.load_registry()["models"] if x["name"] == name), None)
        if m is None:
            return None
        p = JGenParticipant(m)
        council._bridges.append(p)  # 常任参加者として登録
        council._rebuild_participants()
        return p.name
    p = council.add_bridge(spec)
    council._rebuild_participants()
    return p.name


# ── 2. Omni: 全機能内包チャット ───────────────────────────────────────────────
def launch_omni(secret=None):
    from verantyx_council import Council, replay_trace, ThoughtTrace
    from verantyx_mind import read_user_input
    from memory_guard import GUARD
    import time as _time

    import verantyx_config
    if not verantyx_config.get("memory.enabled", True):
        secret = True
        print(f"{C_SYS}  [Config] memory.enabled=false → シークレットで開始{C_RST}")
    if secret is None:
        secret = yesno("シークレットモードで開始? (記憶を使わない)")
    cfg_lang = verantyx_config.get("generation.language")
    if cfg_lang:
        lsel = None
    else:
        lang_opts = [("自動", "質問の言語に任せる"), ("日本語", "Japanese"),
                     ("English", "English"), ("中文", "Chinese"), ("한국어", "Korean")]
        lsel = choose("応答言語", lang_opts, default=1)
    council = Council(secret=secret)
    if cfg_lang:
        council.language = cfg_lang
        print(f"{C_SYS}  [Config] 応答言語 = {cfg_lang} (/lang で変更可){C_RST}")
    elif lsel and lsel > 1:
        council.language = lang_opts[lsel - 1][1]
        print(f"{C_SYS}  [Lang] 応答言語 = {council.language} (/lang で変更可){C_RST}")
    rounds = "auto"
    escalation = bool(verantyx_config.get("escalation.enabled", True))
    speak_tokens = verantyx_config.get("generation.speak_tokens", "auto")
    lex = [None]
    # 設定で常時参加ブリッジが指定されていれば起動時に招集する
    cfg_bridges = verantyx_config.get("models.bridges", "auto")
    if isinstance(cfg_bridges, list):
        for spec in cfg_bridges:
            try:
                p = council.add_bridge(spec)
                print(f"{C_SYS}  [Config] {p.name} を常時参加として招集{C_RST}")
            except Exception as e:
                print(f"{C_WARN}  [Config] bridge '{spec}' の招集に失敗: {e}{C_RST}")

    # 認知アンカーを初期学習として一度だけ永遠の記憶へ刻む + スキル層を用意
    import cognitive_anchors
    from skill_memory import SkillLibrary, looks_like_feedback
    if cognitive_anchors.seed_into_memory(council):
        print(f"{C_SYS}  [Anchor] 認知アンカーを初期学習として刻印 "
              f"(知識は{cognitive_anchors.KNOWLEDGE_CUTOFF}まで=時事はweb / ツールは組合せで無限){C_RST}")
    skills = SkillLibrary()
    last_turn = {"task": None, "result": None, "was_agent": False}

    def get_lexicon():
        if lex[0] is None:
            from weight_lexicon import default_lexicon
            lex[0] = default_lexicon()
        return lex[0]

    # ファイル資産のベクトルバックアップ (初回のみ確認)
    import file_vault
    vcfg = file_vault.load_config()
    if not vcfg["asked"] and not secret:
        print(f"\n{C_TITLE}◆ ファイル資産のベクトルバックアップ{C_RST}")
        print(f"{C_SYS}  パソコン内の文書・コードをベクトル化して永遠の記憶に加えると、\n"
              f"  意味検索 (/files) とペルソナ強化ができるようになります。\n"
              f"  原本の複製は保存しません (抜粋とパスのみ)。あとから /vault でも実行可。{C_RST}")
        if yesno("いまベクトル化を始めますか?"):
            roots = ask_text("対象フォルダ (カンマ区切り)", ", ".join(file_vault.DEFAULT_ROOTS))
            vcfg["roots"] = [r.strip() for r in roots.split(",") if r.strip()]
            vcfg["enabled"] = True
        vcfg["asked"] = True
        file_vault.save_config(vcfg)
        if vcfg["enabled"]:
            file_vault.FileVault().build(council.brain, council.tok, council.axes,
                                         roots=vcfg["roots"])

    print(f"\n{C_SYS}  Omni チャット (全機能内包)。'exit' で終了。/help でコマンド一覧{C_RST}")
    print(f"{C_SYS}  長文ペーストOK (改行しても送信されません)。Enter=送信 / Esc+Enter=改行{C_RST}")
    print(f"{C_SYS}  [{GUARD.status()}]{C_RST}")
    if secret:
        print(f"{C_WARN}  [Secret] 記憶の参照も刻印もしません (/secret で再開){C_RST}")
    try:
        while True:
            try:
                text = read_user_input()
            except (KeyboardInterrupt, EOFError):
                break
            if not text or text.lower() in ("exit", "quit", "q"):
                break
            cmd, _, arg = text.strip().partition(" ")

            if cmd == "/help":
                print(f"""{C_SYS}  ── 議論・発話 ──
  (そのまま質問)   評議会がベクトル議論して回答
  /council        議論参加メンバーの表示・追加・解任
  /scout          ローカルモデルの自動探索と役割割り当て
  /convert X      LM Studio/Ollama/HFの隠しフォルダからjgenへ変換
                  (/convert list で候補一覧 · X --lexicon で辞書のみ高速変換)
  /model          発話役の選択 (jgen/Ollama/LM Studio/9B)
  /lang X         応答言語の強制 (ja / en / なしで解除)
  /think on|off   外部モデルの深い思考 (thinking) を許可/禁止
  /tokens N|auto  発話の長さ (auto=EOSで自然終了 / N=固定上限で狭める・広げる)
  /rounds N|auto  議論ラウンド数
  /reflex         ルーターの進化状況 (獲得した反射と発火回数)
  /injections     注入レシピの学習状況 (どこに何を入れると良かったか)
  /skills         学習したスキル (ツール手順) の一覧と状態
  (応答への不満+改善案を言うと学習ループが起動し、予行演習後に自己進化します)
  /fast           エスカレーションの ON/OFF
  /sage           大型モデルを手動招集
  /bridge X       ollama[:model] / lmstudio[:model] を評議会に常時参加
  ── エージェント (手足) ──
  (作業依頼は自動でエージェントに委譲されます。個々の危険操作のみ確認)
  /ask QUESTION   自動委譲を回避して評議会で議論させる
  /agent TASK     web検索/ファイル編集/シェル/アプリ操作つきで実行
  /screen         画面を視覚層に刻印 (立体十字式圧縮 + OCR)
  /see QUERY      視覚層から過去の画面をテキスト検索
  /spatial        Capture操作記憶 (ingest/status/locate/戻して)
                  /spatial ingest <OpenObjectHouseCapture/…>
                  /spatial status
                  /spatial Blue Mug はどこ
                  /spatial book を戻して
  ── 知識・記憶 ──
  /dict WORD      9B重みの静的辞書で連想検索
  /analogy a b c  ベクトル類推 (a:b = c:?)
  /recall QUERY   永遠の記憶を検索
  /vault [DIRS]   パソコン内ファイルのベクトルバックアップ作成/更新
  /vault status   資産層の統計
  /obsidian [PATH|auto|dry]  Obsidian vault → Cortex L3 取り込み
  /files QUERY    資産層の意味検索 (パソコン内を横断)
  /persona        ペルソナ (会話の記憶 + ファイル資産から抽出)
  /secret         記憶バイアスの遮断/再開
  ── システム ──
  /config         設定の表示 · /config set KEY VALUE で保存 (ロール固定など)
                  例: /config set models.worker ornith9b_full
                      /config set models.sage none
                      /config set models.agent_backend ollama:qwen3:8b
  /mem            メモリ使用状況とロード済みモデル
  /traces         思考の軌跡一覧 · /trace ID で再生
  exit{C_RST}""")
            elif cmd == "/config":
                import verantyx_config as vc
                a = arg.split()
                if not a or a[0] == "show":
                    print(f"{C_SYS}  設定ファイル: {vc.CONFIG_PATH}"
                          f" ({'あり' if os.path.exists(vc.CONFIG_PATH) else '未作成 (全て既定値=auto)'}){C_RST}")
                    print(f"{C_SYS}{vc.describe()}{C_RST}")
                    print(f"{C_SYS}  変更は次回のモデルロードから反映されます "
                          f"(ロード済みモデルは /council で解任可){C_RST}")
                elif a[0] == "set" and len(a) >= 3:
                    try:
                        val = vc.set_value(a[1], " ".join(a[2:]))
                        print(f"{C_SYS}  [Config] {a[1]} = {val!r} を保存しました{C_RST}")
                    except Exception as e:
                        print(f"{C_WARN}  [Config] 失敗: {e}{C_RST}")
                elif a[0] == "reset":
                    vc.reset()
                    print(f"{C_SYS}  [Config] 全て既定値 (auto) に戻しました{C_RST}")
                else:
                    print(f"{C_WARN}  使い方: /config [show] | /config set <key> <value> | /config reset{C_RST}")
            elif cmd == "/secret":
                council.memory.enabled = not council.memory.enabled
                state = ("OFF (シークレット: バイアスなし対話)" if not council.memory.enabled
                         else "ON (永遠の記憶をここから再開)")
                print(f"{C_WARN}  [Secret] 記憶 {state}{C_RST}")
            elif cmd == "/sage":
                council._escalate(2, reason=" 手動招集")
            elif cmd == "/fast":
                escalation = not escalation
                print(f"{C_SYS}  エスカレーション {'OFF (0.5B評議会のみで即答)' if not escalation else 'ON'}{C_RST}")
            elif cmd == "/scout":
                import model_scout
                print(f"{C_SYS}── Model Scout: ローカルモデル探索と役割割り当て ──{C_RST}")
                print(f"{C_SYS}{model_scout.report()}{C_RST}")
            elif cmd == "/convert":
                import jgen_forge
                if not arg or arg.strip() == "list":
                    jgen_forge.cmd_sources()
                else:
                    q = arg.split()
                    parts = "lexicon" if "--lexicon" in q else "full"
                    dense = "--svd" not in q  # 既定は高速なDense2D (--svdで立体十字SVD)
                    query = next((w for w in q if not w.startswith("--")), "")
                    if not query:
                        print(f"{C_WARN}  使い方: /convert <名前の一部> [--lexicon] [--svd]{C_RST}")
                    else:
                        try:
                            jgen_forge.cmd_pull(query, dense=dense, parts=parts)
                        except Exception as e:
                            print(f"{C_WARN}  [Forge] 変換失敗: {e}{C_RST}")
            elif cmd == "/council":
                # 現在の議論参加メンバー
                lineup = [("内部評議会", "Commander / Scout x2 / Worker x2 (0.5B, 常任)")]
                removables = []
                if council._worker is not None:
                    lineup.append((council._worker.name, "jgenワーカー"))
                    removables.append(("worker", council._worker.name))
                if council._sage is not None:
                    lineup.append((council._sage.name, "HF大型 (賢者)"))
                    removables.append(("sage", council._sage.name))
                for b in council._bridges:
                    lineup.append((b.name, "外部参加者"))
                    removables.append(("bridge", b.name))
                print(f"{C_SYS}  現在の議論メンバー:{C_RST}")
                for n, d in lineup:
                    print(f"{C_OPT}   - {n}{C_RST}{C_SYS}  {d}{C_RST}")
                act = choose("操作", [("追加", "モデルを議論に参加させる"),
                                      ("削除", "参加を解除する"),
                                      ("戻る", "")], default=3)
                if act == 1:
                    speakers = [s for s in _list_speakers() if s[0] != "router"]
                    sel = choose("参加させるモデル", speakers)
                    if sel:
                        spec = speakers[sel - 1][0]
                        try:
                            name = _add_council_member(spec, council)
                            print(f"{C_SYS}  [Council] {name} が議論に参加{C_RST}"
                                  if name else f"{C_WARN}  [Council] RAM不足等で追加できません{C_RST}")
                        except Exception as e:
                            print(f"{C_WARN}  [Council] 失敗: {e}{C_RST}")
                elif act == 2 and removables:
                    sel = choose("参加解除するモデル",
                                 [(n, k) for k, n in removables])
                    if sel:
                        kind, name = removables[sel - 1]
                        if kind == "worker":
                            council._worker.close(); council._worker = None
                        elif kind == "sage":
                            council._unload_sage()
                        else:
                            b = next(x for x in council._bridges if x.name == name)
                            council._bridges.remove(b)
                        council._rebuild_participants()
                        print(f"{C_SYS}  [Council] {name} を解任{C_RST}")
            elif cmd == "/model":
                speakers = _list_speakers()
                sel = choose("発話役 / 参加モデルを選択", [(s, d) for s, d in speakers])
                if sel:
                    spec = speakers[sel - 1][0]
                    try:
                        name = _make_speaker(spec, council)
                        if name:
                            print(f"{C_SYS}  [Model] 発話役 = {name}{C_RST}")
                        else:
                            print(f"{C_WARN}  [Model] RAM不足などでロードできませんでした{C_RST}")
                    except Exception as e:
                        print(f"{C_WARN}  [Model] 失敗: {e}{C_RST}")
            elif cmd == "/lang":
                langs = {"ja": "Japanese", "en": "English", "zh": "Chinese",
                         "ko": "Korean", "fr": "French", "de": "German", "es": "Spanish"}
                if arg.strip():
                    council.language = langs.get(arg.strip().lower(), arg.strip())
                else:
                    sel = choose("応答言語", [("自動", "質問の言語に任せる")] +
                                 [(k, v) for k, v in langs.items()], default=1)
                    if sel is None or sel == 1:
                        council.language = None
                    else:
                        council.language = list(langs.values())[sel - 2]
                print(f"{C_SYS}  [Lang] 応答言語 = {council.language or '自動'}{C_RST}")
            elif cmd == "/think":
                on = arg.strip().lower() in ("on", "true", "1", "yes")
                n = 0
                for b in council._bridges:
                    if hasattr(b, "allow_thinking"):
                        b.allow_thinking = on
                        n += 1
                fs = council._forced_speaker
                if fs and hasattr(fs[1], "allow_thinking"):
                    fs[1].allow_thinking = on
                    n += 1
                print(f"{C_SYS}  [Think] thinking {'ON (深い推論、遅い)' if on else 'OFF (即答)'}"
                      f" — 対応モデル {n} 件に適用{C_RST}")
            elif cmd == "/mem":
                print(f"{C_SYS}  {GUARD.status()}{C_RST}")
                loaded = []
                if council._worker is not None:
                    loaded.append(f"worker={council._worker.name}")
                if council._sage is not None:
                    loaded.append(f"sage={council._sage.name} (~19GB)")
                loaded += [f"bridge={b.name}" for b in council._bridges]
                if council._forced_speaker:
                    loaded.append(f"speaker={council._forced_speaker[0]}")
                print(f"{C_SYS}  ロード済み: {', '.join(loaded) or 'ルーターのみ'}"
                      f" | 記憶 {'OFF(secret)' if not council.memory.enabled else 'ON'}{C_RST}")
            elif cmd == "/screen":
                try:
                    from vision_memory import VisionMemory
                    node = VisionMemory().imprint_screen(label=arg or "manual /screen")
                    print(f"{C_MEM}  [Vision] ノード #{node['id']} 刻印 | OCR {len(node['L3_ocr'])} 要素 | "
                          f"概念: {', '.join(node['L2_concepts'][:6])}{C_RST}")
                except Exception as e:
                    print(f"{C_WARN}  [Vision] 失敗: {e} (画面収録権限を確認){C_RST}")
            elif cmd == "/see":
                if not arg:
                    print(f"{C_WARN}  使い方: /see <検索語>{C_RST}")
                    continue
                from vision_memory import VisionMemory
                hits = VisionMemory().search_text(arg)
                if not hits:
                    print(f"{C_MEM}  (視覚層に該当なし){C_RST}")
                for node in hits:
                    import time as _t
                    ts = _t.strftime("%m/%d %H:%M", _t.localtime(node["ts"]))
                    print(f"{C_MEM}  #{node['id']} {ts} '{node['label']}' | "
                          f"{', '.join(node['L2_concepts'][:5])} | {node['L3_jpeg']}{C_RST}")
            elif cmd == "/spatial":
                from spatial_episode import SpatialStore
                store = SpatialStore()
                parts = arg.split(None, 1) if arg else []
                sub = parts[0].lower() if parts else "status"
                rest = parts[1] if len(parts) > 1 else ""
                if sub == "ingest":
                    if not rest or not os.path.isdir(rest):
                        print(f"{C_WARN}  使い方: /spatial ingest "
                              f"<OpenObjectHouseCapture/timestamp>{C_RST}")
                    else:
                        pid = store.ingest(rest)
                        print(f"{C_FIN}  ingested {pid}  "
                              f"objects={len(store.pkg.objects())} "
                              f"records={len(store.pkg.records)}{C_RST}")
                elif sub == "status":
                    st = store.status()
                    print(f"{C_SYS}  active={st['active']}  "
                          f"packages={len(st['packages'])}{C_RST}")
                    for p in st["packages"]:
                        mark = "*" if p["id"] == st["active"] else " "
                        print(f"{C_SYS}  {mark}{p['id']}  obj={p.get('objects')} "
                              f"rec={p.get('records')}{C_RST}")
                elif sub == "list":
                    out = store.handle("一覧")
                    if not out.get("ok"):
                        print(f"{C_WARN}  {out.get('error')}{C_RST}")
                    else:
                        for o in out.get("objects") or []:
                            print(f"{C_MEM}  {o.get('displayName') or o['objectID']}  "
                                  f"home={o.get('poseHome')}{C_RST}")
                else:
                    text = arg.strip()
                    if not text:
                        print(f"{C_WARN}  使い方: /spatial ingest|status|list|<指示>{C_RST}")
                    else:
                        out = store.handle(text)
                        if not out.get("ok"):
                            print(f"{C_WARN}  {out.get('error')}{C_RST}")
                        elif out.get("intent") == "locate":
                            print(f"{C_SYS}  locate query={out.get('query')!r}{C_RST}")
                            for h in out.get("hits") or []:
                                print(f"{C_FIN}  {h.get('displayName') or h['objectID']}  "
                                      f"score={h['score']:.2f}  home={h.get('poseHome')}{C_RST}")
                            if not out.get("hits"):
                                print(f"{C_SYS}  (ヒットなし){C_RST}")
                        elif out.get("intent") == "return":
                            print(f"{C_FIN}  return → "
                                  f"{out.get('displayName') or out.get('objectID')}{C_RST}")
                            print(f"{C_SYS}  {out.get('hint')}{C_RST}")
                            print(f"{C_SYS}  returnError={out.get('returnError')}{C_RST}")
                        else:
                            import json as _json
                            print(_json.dumps(out, ensure_ascii=False, indent=2))
            elif cmd == "/recall":
                if not arg:
                    print(f"{C_WARN}  使い方: /recall <検索語>{C_RST}")
                    continue
                hits = council.memory_search(arg, k=5)
                if not hits:
                    print(f"{C_MEM}  (記憶なし){C_RST}")
                for h in hits:
                    l2 = f" | {','.join(h['concepts'][:4])}" if h.get("concepts") else ""
                    print(f"{C_MEM}  sim={h['score']:.3f}{l2}  {h['text'][:110]}{C_RST}")
            elif cmd == "/vault":
                import file_vault
                vault = file_vault.FileVault()
                if arg.strip() == "status" or not arg.strip():
                    st = vault.stats()
                    cfg = file_vault.load_config()
                    print(f"{C_MEM}  [Vault] {st['files']} ファイル / {st['chunks']} チャンク "
                          f"({st['bytes']//2**20}MB のベクトル) | 対象: {', '.join(cfg['roots'])}{C_RST}")
                    if st["top_ext"]:
                        print(f"{C_MEM}  内訳: " +
                              ", ".join(f"{e or '(なし)'}x{n}" for e, n in st["top_ext"]) + C_RST)
                    if arg.strip() == "status":
                        continue
                if council.memory.enabled:
                    cfg = file_vault.load_config()
                    if arg.strip() and arg.strip() != "status":
                        cfg["roots"] = [r.strip() for r in arg.split(",") if r.strip()]
                    cfg["enabled"] = True
                    file_vault.save_config(cfg)
                    vault.build(council.brain, council.tok, council.axes,
                                roots=cfg["roots"])
                else:
                    print(f"{C_WARN}  [Vault] シークレット中は索引を更新しません{C_RST}")
            elif cmd == "/files":
                if not arg:
                    print(f"{C_WARN}  使い方: /files <検索語>{C_RST}")
                    continue
                import file_vault
                from verantyx_mind import embed_text
                vault = file_vault.FileVault()
                qv = embed_text(council.brain, council.tok, arg)
                hits = vault.search(qv, k=6)
                if not hits:
                    print(f"{C_MEM}  (資産層に該当なし。/vault で索引を作成){C_RST}")
                for node, sim in hits:
                    print(f"{C_MEM}  sim={sim:.3f}  {node['L3_path']}:{node['L3_line']}{C_RST}")
                    print(f"{C_SYS}    {node['L3_excerpt'][:100].replace(chr(10), ' ')}{C_RST}")
            elif cmd == "/obsidian":
                import obsidian_ingest
                dry = arg.strip() in ("dry", "dry-run", "--dry-run")
                path_arg = "auto" if (not arg.strip() or dry) else arg.strip()
                if not council.memory.enabled and not dry:
                    print(f"{C_WARN}  [Obsidian] シークレット中は取り込みしません{C_RST}")
                    continue
                vault = obsidian_ingest.resolve_vault(path_arg)
                if not vault:
                    print(f"{C_WARN}  Obsidian vault が見つかりません。"
                          f" /obsidian /path/to/vault か VERANTYX_OBSIDIAN_VAULT{C_RST}")
                    continue
                print(f"{C_MEM}  [Obsidian] vault={vault}"
                      f"{' (dry-run)' if dry else ''}{C_RST}")
                stats = obsidian_ingest.ingest(
                    council.brain, council.tok, council.axes, council.memory,
                    vault, limit=80, dry_run=dry, quiet=False)
                print(f"{C_MEM}  [Obsidian] {stats}{C_RST}")
            elif cmd == "/bridge":
                try:
                    council.add_bridge(arg or "ollama")
                except Exception as e:
                    print(f"{C_WARN}  bridge失敗: {e}{C_RST}")
            elif cmd == "/rounds":
                rounds = arg if arg in ("", "auto") else arg
                rounds = rounds or "auto"
                print(f"{C_SYS}  rounds = {rounds}{C_RST}")
            elif cmd == "/tokens":
                a = arg.strip().lower()
                if a in ("", "auto"):
                    speak_tokens = "auto"
                    print(f"{C_SYS}  [Tokens] auto: EOSで自然に終了 (途切れは文境界で整形)。"
                          f"天井 512 (0.5B) / 1024 (大型){C_RST}")
                elif a.isdigit():
                    speak_tokens = int(a)
                    print(f"{C_SYS}  [Tokens] 固定上限 = {speak_tokens} tokens{C_RST}")
                else:
                    print(f"{C_WARN}  使い方: /tokens auto | /tokens 200 (狭める) | /tokens 2000 (広げる){C_RST}")
            elif cmd == "/agent":
                if not arg:
                    print(f"{C_WARN}  使い方: /agent <タスク>{C_RST}")
                    continue
                r = _run_agent_inline(arg, memorize=council.memory.enabled,
                                      language=council.language)
                if council.memory.enabled:
                    import session_log
                    session_log.log_turn("agent", arg, r)
            elif cmd == "/dict":
                if not arg:
                    print(f"{C_WARN}  使い方: /dict <語>{C_RST}")
                    continue
                for t, s in get_lexicon().associate(arg):
                    print(f"{C_MEM}  {arg} ~ {t}  ({s:.3f}){C_RST}")
            elif cmd == "/analogy":
                parts = arg.split()
                if len(parts) != 3:
                    print(f"{C_WARN}  使い方: /analogy man king woman{C_RST}")
                    continue
                for t, s in get_lexicon().analogy(*parts):
                    print(f"{C_MEM}  {parts[0]}:{parts[1]} = {parts[2]}:{t}  ({s:.3f}){C_RST}")
            elif cmd == "/traces":
                for rec in ThoughtTrace().list()[-15:]:
                    print(f"{C_SYS}  {rec['trace_id']}  "
                          f"{_time.strftime('%m/%d %H:%M', _time.localtime(rec['ts']))}  "
                          f"esc={rec['escalation_level']}  {rec['question'][:44]}{C_RST}")
            elif cmd == "/trace":
                if arg:
                    replay_trace(arg)
            elif cmd == "/persona":
                p = council.memory.persona()
                if p:
                    print(f"{C_MEM}  [Persona/会話] " + ", ".join(f"{n}({v:+.2f})" for n, v in p) + C_RST)
                else:
                    print(f"{C_MEM}  [Persona/会話] 無効 (シークレット中か記憶不足){C_RST}")
                import file_vault
                fp = file_vault.FileVault().persona(council.axes)
                if fp:
                    print(f"{C_MEM}  [Persona/資産] " + ", ".join(f"{n}({v:.2f})" for n, v in fp) +
                          f"{C_SYS}  ← パソコン内ファイルの6軸分布{C_RST}")
                else:
                    print(f"{C_SYS}  [Persona/資産] 資産層が未構築です (/vault で作成){C_RST}")
            elif cmd == "/reflex":
                st = council.reflex.stats()
                print(f"{C_SYS}  [Reflex] 獲得した反射 {st['reflexes']} 件 / "
                      f"発火 {st['fires']} 回 / 脆かった問題 {st['fragile']} 件{C_RST}")
                for n in council.reflex.index[-8:]:
                    print(f"{C_SYS}    esc{n['esc_level']} r{n['rounds']} "
                          f"{'脆' if n.get('fragile') else '頑'} hits={n.get('hits',0)}  "
                          f"[{n.get('intent','chat')}] {n['question'][:50]}{C_RST}")
            elif cmd == "/injections":
                rows = council.injections.summary(12)
                print(f"{C_SYS}  [Injection] 学習済みレシピ {len(council.injections.index)} 件{C_RST}")
                for n in rows:
                    print(f"{C_SYS}    {n.get('recipe','?'):12s} "
                          f"✓{n.get('successes',0)} ✗{n.get('failures',0)}  "
                          f"{n.get('question','')[:48]}{C_RST}")
            elif cmd == "/skills":
                st = skills.stats()
                print(f"{C_SYS}  [Skills] 獲得スキル {st['skills']} 件 "
                      f"{st['by_status']} / 適用 {st['hits']} 回{C_RST}")
                for n in skills.index[-8:]:
                    mark = {"proven": "✅", "proposed": "…", "demoted": "✗"}.get(
                        n.get("status"), "?")
                    print(f"{C_SYS}   {mark} score={n.get('score',0):.2f} "
                          f"[{n.get('status')}] {n['task_kind'][:40]}{C_RST}")
                    print(f"{C_SYS}      {n['plan'][:80].replace(chr(10),' ')}{C_RST}")
            elif cmd == "/ask":
                # 自律ルーティングを回避して強制的に評議会で議論する
                if arg:
                    rec = council.ask(arg, rounds=rounds, escalation=escalation,
                                      speak_tokens=speak_tokens,
                                      memorize=council.memory.enabled)
                    if council.memory.enabled:
                        import session_log
                        session_log.log_turn("council", arg, (rec or {}).get("answer"))
                    GUARD.maybe_trim(); GUARD.check_critical()
                else:
                    print(f"{C_WARN}  使い方: /ask <質問>{C_RST}")
            elif cmd.startswith("/"):
                print(f"{C_WARN}  不明なコマンド: {cmd} (/help 参照){C_RST}")
            else:
                from verantyx_mind import embed_text
                from intent_router import (route as route_intent, learn_intent,
                                           looks_like_route_correction)
                from router_classifier import wrap_for_classify
                # ── フィードバック: ルート修正 or 手順学習 ──
                force_intent = None
                if last_turn["task"] and council.memory.enabled:
                    want = looks_like_route_correction(text)
                    if want and last_turn.get("was_agent") != (want == "task"):
                        print(f"{C_TITLE}  ◆ ルート修正学習{C_RST}")
                        print(f"{C_SYS}  直前を '{want}' として学習し直します{C_RST}")
                        qv = embed_text(council.brain, council.tok, last_turn["task"])
                        learn_intent(council.reflex, council.brain, qv,
                                     last_turn["task"], want)
                        if want == "task":
                            text = last_turn["task"]  # 同じ依頼をエージェントで再実行
                            force_intent = "task"
                        else:
                            last_turn["task"] = None
                            continue
                    elif looks_like_feedback(text):
                        if last_turn.get("was_agent"):
                            _learn_from_feedback(council, skills, last_turn, text)
                        else:
                            _learn_injection_feedback(council, last_turn, text)
                        last_turn["task"] = None
                        continue
                    else:
                        from injection_policy import looks_like_quality_feedback
                        if (not last_turn.get("was_agent")
                                and looks_like_quality_feedback(text)):
                            # 評議会回答への「違う/正しい」系 — 注入レシピを強化/弱化
                            _learn_injection_feedback(council, last_turn, text)
                            last_turn["task"] = None
                            continue
                # ── 入口ルーティング: classify-only (generate 禁止) ──
                if force_intent:
                    intent = force_intent
                    qv = embed_text(council.brain, council.tok, text)
                    print(f"{C_SYS}  [Router] {intent} ← correction{C_RST}")
                else:
                    # API 境界: 分類は ClassifyOnlyBrain 経由 (speak/council とは別入口)
                    clf_brain = wrap_for_classify(council.brain)
                    decision = route_intent(
                        text, clf_brain, council.tok,
                        reflex=council.reflex if council.memory.enabled else None,
                        memory_enabled=council.memory.enabled,
                        dictionary=council.dict,
                        axes=getattr(council, "axes", None))
                    intent = decision["intent"]
                    qv = decision.get("qvec")
                    conf = decision.get("confidence")
                    amb = decision.get("ambiguous")
                    conf_s = f" conf={conf:.2f}" if isinstance(conf, (int, float)) else ""
                    amb_s = " ambiguous" if amb else ""
                    lbl = decision.get("label")
                    lbl_s = f" label={lbl}" if lbl and lbl != intent else ""
                    print(f"{C_SYS}  [Router] {intent} ← {decision['source']}"
                          f"{conf_s}{amb_s}{lbl_s}"
                          f"{(' | ' + decision['detail']) if decision['detail'] else ''}{C_RST}")
                if intent == "task":
                    print(f"{C_SYS}  → エージェント (手足) を使います"
                          f" (議論に回すには /ask <質問>){C_RST}")
                    if qv is None:
                        qv = embed_text(council.brain, council.tok, text)
                    hint = None
                    if council.memory.enabled:
                        plan = skills.best_plan(qv)
                        if plan:
                            hint = plan["plan"]
                            print(f"{C_SYS}  [Skill] 学習済みの手順を適用 "
                                  f"(sim {plan['sim']:.2f}, score {plan['score']:.2f}){C_RST}")
                    result = _run_agent_inline(text, memorize=council.memory.enabled,
                                               language=council.language, skill_hint=hint)
                    last_turn.update(task=text, result=result, was_agent=True)
                    if council.memory.enabled:
                        learn_intent(council.reflex, council.brain, qv, text, "task")
                        import session_log
                        session_log.log_turn("agent", text, result)
                    GUARD.maybe_trim(); GUARD.check_critical()
                    continue
                rec = council.ask(text, rounds=rounds, escalation=escalation,
                                  speak_tokens=speak_tokens,
                                  memorize=council.memory.enabled)
                last_turn.update(task=text, result=(rec or {}).get("answer"),
                                 was_agent=False,
                                 injection_recipe=(rec or {}).get("injection_recipe"))
                # chat の反射刻印は council.ask 内で行う (esc/rounds 付き)
                if council.memory.enabled:
                    import session_log
                    session_log.log_turn("council", text, (rec or {}).get("answer"))
                GUARD.maybe_trim(); GUARD.check_critical()
    finally:
        council.close()


def _learn_injection_feedback(council, last_turn, feedback):
    """評議会の回答へのフィードバックで、直前の注入レシピを強化/弱化する。
    否定なら次に試すべき代替レシピ (plan_steal / early_steal / deep_rounds) も刻印する。"""
    from verantyx_mind import embed_text
    from injection_policy import looks_like_positive, looks_like_negative

    print(f"{C_TITLE}  ◆ 注入レシピ学習{C_RST}")
    print(f"{C_SYS}  直前の評議会回答への指摘として解釈{C_RST}")
    qv = embed_text(council.brain, council.tok, last_turn["task"])
    used = (last_turn.get("injection_recipe")
            or getattr(council, "_last_injection", "none"))
    nid = getattr(council, "_last_injection_id", None)

    if looks_like_positive(feedback):
        if nid is not None:
            council.injections.reinforce(nid, success=True)
        else:
            council.injections.record(qv, last_turn["task"], recipe=used,
                                      success=True, brain=council.brain)
        print(f"{C_FIN}  ✅ 注入レシピ '{used}' を強化しました{C_RST}")
        return

    # 否定 / 修正: 使ったレシピを弱化し、より強い介入を候補として刻印
    if nid is not None:
        council.injections.reinforce(nid, success=False)
    else:
        council.injections.record(qv, last_turn["task"], recipe=used,
                                  success=False, fragile=True, brain=council.brain)
    alt = {"none": "plan_steal", "plan_steal": "early_steal",
           "early_steal": "deep_rounds", "deep_rounds": "early_steal"}.get(used, "plan_steal")
    council.injections.record(qv, last_turn["task"], recipe=alt,
                              success=True, brain=council.brain,
                              meta={"from_feedback": True, "replaced": used})
    print(f"{C_WARN}  ✗ '{used}' を弱化。次回同種問題では '{alt}' を試します{C_RST}")


def _learn_from_feedback(council, skills, last_turn, feedback):
    """ユーザーの修正フィードバックからスキルを獲得し、ペルソナ擬似シミュレーションで
    予行演習してから (良ければ) proven スキルとして学習する。"""
    from verantyx_mind import embed_text
    print(f"{C_TITLE}  ◆ フィードバック学習ループ{C_RST}")
    print(f"{C_SYS}  直前: 「{last_turn['task'][:50]}」への指摘として解釈{C_RST}")
    # 1) 提案されたやり方を「手順」として抽出 (頭脳に整形させる)
    backend = _get_agent_backend()
    plan_msgs = [
        {"role": "system", "content":
         "Extract a concise, reusable tool-plan from the user's feedback. Output ONLY "
         "an ordered list of tool steps (web_search, fetch, read_file, write_file, "
         "shell, open_app, click, etc.) that would satisfy this kind of request next "
         "time. 3-6 short imperative steps."},
        {"role": "user", "content":
         f"Original request: {last_turn['task']}\n"
         f"What I actually got: {(last_turn.get('result') or '')[:300]}\n"
         f"My feedback: {feedback}"},
    ]
    try:
        plan = backend.complete(plan_msgs, max_tokens=200).strip()
    except Exception as e:
        # サーバー側のモデル差し替え等で死んだ接続を作り直して1回だけ再試行
        print(f"{C_SYS}  [Skill] 頭脳が応答不能 ({str(e)[:80]})。再接続して再試行{C_RST}")
        try:
            backend = _reset_agent_backend()
            plan = backend.complete(plan_msgs, max_tokens=200).strip()
        except Exception as e2:
            print(f"{C_WARN}  [Skill] 手順抽出に失敗: {e2}{C_RST}")
            return
    print(f"{C_SYS}  抽出した手順:\n{_indent_plan(plan)}{C_RST}")
    qv = embed_text(council.brain, council.tok, last_turn["task"])
    node = skills.learn(qv, task_kind=last_turn["task"], plan=plan,
                        brain=council.brain)
    if node is None:
        print(f"{C_WARN}  [Skill] ベクトル介入可能なモデルが無いため学習をスキップ{C_RST}")
        return
    # ルートも task として刻印 (次回は入口からエージェントへ)
    from intent_router import learn_intent
    learn_intent(council.reflex, council.brain, qv, last_turn["task"], "task")
    # 2) ペルソナに対する擬似シミュレーション (実行せず満足度を予測)
    persona = council.memory.persona() if council.memory.enabled else []
    print(f"{C_SYS}  [Rehearsal] ペルソナに対して予行演習中...{C_RST}")
    score, note = skills.rehearse(node, last_turn["task"], persona, backend)
    print(f"{C_SYS}  予行演習スコア {score:.2f} — {note.splitlines()[0][:80]}{C_RST}")
    # 3) 良ければ学習 (proven に昇格)。次回から同種タスクで自動適用される
    from skill_memory import PROMOTE_SCORE
    if score >= PROMOTE_SCORE:
        skills.promote(node)
        print(f"{C_FIN}  ✅ 予行演習に合格。この手順を学習しました "
              f"(次回から同種の依頼で自動適用){C_RST}")
    else:
        print(f"{C_WARN}  予行演習が基準未満。候補として保持しますが自動適用はしません{C_RST}")


def _indent_plan(s):
    return "\n".join("    " + l for l in s.splitlines() if l.strip())


def _ensure_agent_ctx():
    global _AGENT_CTX
    import verantyx_agent as va
    if _AGENT_CTX is None:
        import verantyx_config
        spec = verantyx_config.get("models.agent_backend", "auto")
        backend = va.make_backend(spec)
        print(f"{C_SYS}  [Agent] 頭脳: {backend.name}{C_RST}")
        mem = va.MemoryTool()
        tools = va.build_tools(mem, va.Confirmer())
        _AGENT_CTX = (backend, tools, mem)
    return _AGENT_CTX


def _get_agent_backend():
    """フィードバック学習の手順抽出/予行演習に使う頭脳 (エージェントと共有)。"""
    return _ensure_agent_ctx()[0]


def _reset_agent_backend():
    """バックエンドが死んだ (モデル差し替え/サーバー再起動) 時に作り直す。"""
    global _AGENT_CTX
    _AGENT_CTX = None
    return _ensure_agent_ctx()[0]


def _run_agent_inline(task, memorize=True, language=None, skill_hint=None):
    """チャットの中から単発でエージェントを走らせ、最終回答文字列を返す。"""
    import verantyx_agent as va
    backend, tools, mem = _ensure_agent_ctx()
    return va.run_agent(task, backend, tools, memory_tool=mem, memorize=memorize,
                        language=language, skill_hint=skill_hint)


_AGENT_CTX = None


# ── 3. エージェント ──────────────────────────────────────────────────────────
def launch_agent():
    backend = ask_text("頭脳 (auto/lmstudio[:model]/ollama[:model]/sage)", "auto")
    secret = yesno("シークレット? (タスク結果を記憶に刻印しない)")
    auto_yes = yesno("shell 実行の確認を省略する? (危険)")
    import verantyx_agent
    sys.argv = ["verantyx_agent.py", "--backend", backend]
    if secret:
        sys.argv.append("--secret")
    if auto_yes:
        sys.argv.append("--yes")
    verantyx_agent.main()


# ── 4. 静的辞書 ──────────────────────────────────────────────────────────────
def launch_lexicon():
    from weight_lexicon import default_lexicon
    lex = default_lexicon()
    print(f"{C_SYS}  [Lexicon] {lex.name}: vocab={lex.vocab:,} hidden={lex.hidden} "
          f"(mmap読み取りのみ、フォワードなし){C_RST}")
    print(f"{C_SYS}  語を入力すると重み空間の連想を引く。'a : b = c' で類推。'exit' で終了{C_RST}")
    while True:
        try:
            q = input("\n📖 ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not q or q.lower() in ("exit", "quit", "q"):
            break
        if "=" in q and ":" in q:
            try:
                ab, c = q.split("=")
                a, b = ab.split(":")
                pairs = lex.analogy(a.strip(), b.strip(), c.strip().rstrip("?:"))
                for t, s in pairs:
                    print(f"{C_MEM}  -> {t}  ({s:.3f}){C_RST}")
            except ValueError:
                print(f"{C_WARN}  形式: man : king = woman{C_RST}")
        else:
            for t, s in lex.associate(q):
                print(f"{C_MEM}  {q} ~ {t}  ({s:.3f}){C_RST}")


# ── 5. 思考の軌跡 ────────────────────────────────────────────────────────────
def launch_traces():
    import time as _time
    from verantyx_council import ThoughtTrace, replay_trace
    recs = ThoughtTrace().list()
    if not recs:
        print(f"{C_SYS}  軌跡はまだありません{C_RST}")
        return
    for i, rec in enumerate(recs[-20:], 1):
        print(f"{C_OPT}  {i:2d}. {rec['trace_id']}  "
              f"{_time.strftime('%m/%d %H:%M', _time.localtime(rec['ts']))}  "
              f"esc={rec['escalation_level']}  {rec['question'][:44]}  ->  {rec['answer'][:36]}{C_RST}")
    sel = ask_text("再生する番号 (Enterで戻る)")
    if sel.isdigit() and 1 <= int(sel) <= len(recs[-20:]):
        replay_trace(recs[-20:][int(sel) - 1]["trace_id"])


# ── 6. 記憶 ──────────────────────────────────────────────────────────────────
def launch_memory():
    from transformers import AutoTokenizer
    from verantyx_mind import (DEFAULT_MODEL, TOKENIZER, AxisAnchors,
                               CortexMemory, RustBrain, embed_text)
    memory = CortexMemory(AxisAnchors())
    print(f"{C_MEM}  [Cortex Memory] ノード {len(memory.index)} 件{C_RST}")
    p = memory.persona()
    if p:
        print(f"{C_MEM}  [Persona] " + ", ".join(f"{n}({v:+.2f})" for n, v in p) + C_RST)
    brain, tok = None, None
    print(f"{C_SYS}  検索語を入力 (exit で戻る){C_RST}")
    try:
        while True:
            try:
                q = input("\n🔎 ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not q or q.lower() in ("exit", "quit", "q"):
                break
            if brain is None:
                tok = AutoTokenizer.from_pretrained(TOKENIZER)
                brain = RustBrain(DEFAULT_MODEL)
            qv = embed_text(brain, tok, q)
            rows = memory.search(qv, k=6, query_text=q)
            if not rows:
                print(f"{C_MEM}  (該当なし){C_RST}")
            for text, sim, _, concepts, _nid in rows:
                l2 = f" | {','.join(concepts[:4])}" if concepts else ""
                print(f"{C_MEM}  sim={sim:.3f}{l2}  {text[:110]}{C_RST}")
    finally:
        if brain is not None:
            brain.close()


# ── Demo: 複数ターミナルで評議会を可視化 ─────────────────────────────────────
def launch_demo():
    """デモモード。使い勝手低下を明記し、yes/no で承認してから舞台を開く。"""
    from demo_stage import confirm_demo, DemoStage, DemoCouncilHook
    from verantyx_council import Council
    from verantyx_mind import read_user_input

    if not confirm_demo():
        return

    print(f"{C_SYS}  [Demo] 画面を検知し、映像壁＋起動帯を配置しています…{C_RST}")
    stage = DemoStage()
    stage.open()
    hook = DemoCouncilHook(stage)

    council = Council(secret=True)  # デモは記憶汚染を避ける
    council.demo = hook
    council.quiet = False
    orient = stage.meta.get("screen", {}).get("orient", "?")
    sw = stage.meta.get("screen", {}).get("w", 0)
    sh = stage.meta.get("screen", {}).get("h", 0)
    print(f"{C_FIN}  [Demo] 舞台準備完了 ({orient} {sw}×{sh})。"
          f"このターミナル(YOU)は下帯にあります。{C_RST}")
    print(f"{C_SYS}  'exit' で永遠記憶アニメのあと全デモ窓を閉じます。{C_RST}")

    try:
        while True:
            hook.on_input_wait()
            stage.write("INPUT", "▶ 質問を入力してください…")
            print(f"{C_OPT}🧑 You (Demo):{C_RST} ", end="", flush=True)
            try:
                text = read_user_input()
            except (KeyboardInterrupt, EOFError):
                print()
                break
            hook.on_input_done()
            if not text or not str(text).strip():
                continue
            text = str(text).strip()
            if text.lower() in ("exit", "quit", "q"):
                break
            stage.write("INPUT", f"You: {text}")
            stage.broadcast(f"◆ 質問受信: {text[:60]}")
            try:
                council.ask(text, rounds="auto", escalation=True,
                            memorize=False, perturb_test=True)
            except Exception as e:
                stage.broadcast(f"[error] {e}")
                print(f"{C_WARN}  [Demo] エラー: {e}{C_RST}")
    finally:
        stage.close()
        council.close()


MODES = [
    ("Omni",     "全機能内包: 議論/エージェント/辞書/視覚/記憶 (/help)", launch_omni),
    ("Demo",     "評議会の可視化デモ (複数ターミナル・使い勝手低下・要承認)", launch_demo),
    ("Mind",     "可視化つきベクトル思考 + 永遠の記憶 (1ターン~2秒)", launch_mind),
    ("Agent",    "手足つき: web検索 / ファイル編集 / アプリ操作", launch_agent),
    ("辞書",     "9B重みを発火させずに連想検索 (静的辞書)", launch_lexicon),
    ("軌跡",     "過去の議論ベクトルを一覧・再生", launch_traces),
    ("記憶",     "永遠の記憶の検索 / ペルソナ", launch_memory),
]


def main():
    banner()
    detect_environment()
    while True:
        sel = choose("モードを選択", [(n, d) for n, d, _ in MODES], default=1)
        if sel is None:
            print(f"{C_SYS}  bye{C_RST}")
            return
        try:
            MODES[sel - 1][2]()
        except SystemExit:
            pass
        except KeyboardInterrupt:
            print()
        print(f"\n{C_SYS}  ── メニューに戻ります ──{C_RST}")


if __name__ == "__main__":
    main()
