# Router / Divergence Architecture Plan

入口ルーターを「分類専用の神経境界」に分離し、評議会はパズル＋立体十字（AxisAnchors）＋発散交換で 0.5B 単体精度を上げる。  
**BABEL / codec パリティは本計画の対象外**（別トラック）。

正本の実装計画フェーズ: **0–5**（本ドキュメントとコード公理を同期）。

---

## 公理 (Design axioms)

1. **Router = 正確な分類器であり知性ではない**  
   回答・熟考・計画をしない。埋め込みで柔軟に分類する（キーワード一本槍にしない）。ミニ推論器にしない。
2. **Router インスタンスはクローンであってはならない / 分身禁止**  
   同じ脳ハンドルが council / speak もできるなら専門化は嘘。ルーター経路は **ClassifyOnlyBrain のみ**。speak / deliberate は別エントリ（同一ウェイトの別ラッパ可・プロセス二重ロードはしない）。
3. **0.5B-only accuracy path**  
   `plan_steal` / 大型エスカレーションは **一時的フォールバック**として残す。削除しない。
4. **ChatML / temperature / repetition-penalty を主ブーストにしない**  
   二次制御は可。戦略の中心は情報粒・軸分解・発散交換。
5. **Information grain（命題サイズ）**  
   全文一発投入でもトークン破片でもなく、命題サイズ（`PROP_MIN`/`PROP_MAX`）。
6. **パズル + 立体十字 (AxisAnchors) + pass order**  
   エネルギー分解 → 軸/役割の独立推論 → 発散交換（長い NL 討論ではない）→ join → 単一 speak。  
   Matryoshka はゲート後 **エネルギー降順**で軸を渡す。
7. **Personality vectors / axis inject**  
   キャリアとしての軸ベクトル注入は Phase 5 最小版（`AxisAnchors.anchors[i]` を小さい α で加算）。フル人格学習は後続。

### 明示的な位置づけ

ルーターは **記号境界上の神経分類器 (neuro classifier at the symbolic boundary)** である。  
古典的な記号 AI（ルールエンジンで世界を推論する）ではない。ニューラル埋め込み／次トークン分布で離散ラベルを出し、その先の記号的分岐（agent vs council）に渡す。

---

## Non-goals

- BABEL パリティ / codec スプリント
- 生成でルーターを「賢く」する（曖昧解消のための `generate()` 禁止）
- `plan_steal` / escalation の削除
- 本線に長い NL `_nl_generate` 討論を載せる

---

## Target flow

```text
UserText → router_classifier.classify → task→Agent / chat→Council.ask
  → Round0 independent (no shared soft)
  → DivergencePacket per role/axis
  → DivergenceExchange + score S_i = aC + bE − cR + dN
  → low divergence → provisional consensus (weighted by S_i, not majority)
  → high divergence → reinfer split roles once (proposition-sized hint)
       else fallback _escalate / _plan_steal
  → PuzzleJoin → Single speak
```

Matryoshka は同型の核を共有する別入口（エネルギー分解 → 軸独立 → 接合）。

---

## Current vs Target

| | Current / Done | Target |
|---|---|---|
| 入口 | `router_classifier.classify` + Omni `wrap_for_classify` | 維持。confidence / ambiguous をログ明示 |
| 脳ハンドル | classify = `ClassifyOnlyBrain`；speak/deliberate は別論理ハンドル | プロセス二重ロードなし |
| 曖昧時 | `ambiguous=True` + 保守デフォルト | 生成で解消しない |
| 評議会 | 独立 R0 → DivergencePacket → C/E/R/N 交換 → join → speak | 本線。NL 討論は対照実験のみ |
| 精度ブースト | plan_steal / 大型 escalate（残置） | 0.5B 本線を先に伸ばし、escalate は一時フォールバック |

---

## Phases

### Phase 0 — 計画の正本と受け入れ確認

**Goals**
- 本ドキュメントをフェーズ 0–5・C/E/R/N・渡し順・測定と同期
- `scripts/smoke_router_classify.py` 緑、`ClassifyOnlyBrain.generate` 例外、Omni が `wrap_for_classify` 経由

**Acceptance**
- [x] 公理がドキュメントとコードで一致（Phase 1 骨格）
- [x] `--no-model` スモーク緑

### Phase 1 — ルーター分類機（完了・差分込み）

**Goals**
- `{label, confidence, scores?, ambiguous}` を返す分類専用 API
- 経路内で `generate()` 禁止（`ClassifyOnlyBrain`）
- Omni 入口を classifier 経由に配線；ログに confidence / ambiguous
- **ルーティング精度 ≠ QA**（`benchmarks/intent_router_eval.py` が routing の正）

**Acceptance**
- [x] `classify()` / `route()` が回答テキストを返さない
- [x] classifier 経路で `brain.generate` を呼ぶと例外
- [x] Omni が `task` / `chat`（search→task 正規化）を維持
- [x] 低信頼時 `ambiguous=True` かつ保守デフォルト（生成なし）
- [x] スモークスクリプトが label+confidence を表示
- [x] 指標分離を README / 本計画に記載

### Phase 2 — Independent round-0 + DivergencePacket

**Goals**
- 各軸/役割が **他者出力を見ずに** round-0 推論
- `(z, dist)` → `make_round0_packet` / 共通ヘルパで `DivergencePacket`
- `grain_ok` 未満はクリップ／1命題に正規化
- `ask()` 戻り値に `divergence_packets`（後方互換キー維持）

**Acceptance**
- [x] round-0 が並列独立（交差汚染なし；R0 に他者 soft なし）
- [x] Packet が命題サイズ
- [x] `Council.ask` / `MatryoshkaCouncil.ask` でパケット列が戻り値に出る

### Phase 3 — Divergence exchange + C/E/R/N（非多数決）

**Goals**
- パケット間発散量: 隠れ cos、分布重なり、命題キー差分（`PuzzleJoiner` 指標再利用可）
- \(S_i = a C_i + b E_i - c R_i + d N_i\)（係数は定数テーブル）
  - **C**: 確信度（エントロピー逆数 / packet.confidence）
  - **E**: 証拠整合（記憶ヒット or factual 質量。無ければ 0）
  - **R**: 他パケットとの矛盾・リスク
  - **N**: 他にない新規キー
- 乖離小 → 仮合意（加重は S_i、単純多数決しない）
- 乖離大 → 割れた軸／役割だけ再推論 1 回；だめなら `_escalate` / `_plan_steal`
- トレース: `divergence` / `S_i` / `joined|reinfer|escalate`
- fair（escalate off）でも reinfer まで動く
- NL `_nl_generate` は本線に載せない

**Acceptance**
- [x] 交換がベクトル/packet 主導
- [x] fair escalate=off で reinfer 可

### Phase 4 — パズル渡し順 + 接合 + 発話ハンドル分離

**Goals**
- Matryoshka: ゲート後エネルギー降順で独立 `opine`（depth=0 は `context_soft=None`；join 後のみ depth>0 に soft）
- `PuzzleJoiner` drop 閾値を乖離と連動（クラスタサイズ&lt;2 のときのみ全採用フォールバック）
- speak は 1 回。`ClassifyOnlyBrain` では speak しない

**Acceptance**
- [x] 軸処理順がエネルギー降順
- [x] drop がベンチで非ゼロになりうる
- [x] speak 経路が classify ラッパを通らない

### Phase 5 — 公平測定 + 軸キャリア最小注入

**Goals**
- ベンチモード `council_div` / `puzzle_div`: escalate off、`force_router_speaker`、同一 0.5B
- 主戦場: `hard_elevated`（易しい factual は天井確認のみ）
- 軸キャリア最小: `AxisAnchors.anchors[i]` を該当 `AxisSlot` に小さい α で soft／加算
- README 主張境界: 構造は探索・誤り検出を改善。世界知識は増えない。plan_steal は別経路。routing ≠ QA

**Acceptance**
- [x] 公平ベンチ結果が `benchmarks/results/` に保存
- [x] ルーティング accuracy と QA を混同しない記述

---

## How to measure

### A. Routing accuracy（QA と分離）

- データ: `benchmarks/datasets/intent_routing.jsonl`
- ランナー: `benchmarks/intent_router_eval.py` / `scripts/smoke_router_classify.py`
- 指標: accuracy, task P/R/F1, source 内訳, **ambiguous 率**, confidence calibration（将来）
- **禁止**: ルーティング正答率に QA 正答を混ぜない。`intent_router_eval` が routing の正本。

### B. Deliberation / QA（公平 0.5B speaker）

- `force_router_speaker=True`（または `--no-escalate` がそれを含意）で発話役を 0.5B に固定
- council / matryoshka / `*_div` の差分は **同一 speaker** 上で測る
- plan_steal / 大型 escalate を入れた条件は別ラベルで報告（本線と混同しない）
- 主戦場: `benchmarks/datasets/hard_elevated.jsonl`（multihop）。易問同点は失敗とみなさない

### C. 情報粒

- Packet あたりの命題長・個数の分布をトレースに残す
- 「全文ダンプ」と「1語破片」の両極端を `grain_ok` で拒否／正規化

---

## Phase 1 実装メモ（参照）

| モジュール | 役割 |
|---|---|
| `router_classifier.py` | 分類専用 API + `ClassifyOnlyBrain` |
| `intent_router.py` | 既存 `route` / 学習 API。classifier に委譲 |
| `divergence_packet.py` | DivergencePacket + round-0 ヘルパ |
| `divergence_exchange.py` | 乖離交換 + C/E/R/N + join/reinfer |
| `scripts/smoke_router_classify.py` | label+confidence スモーク |
| Omni (`verantyx.py`) | `classify` / `route` 経由。confidence・ambiguous 表示 |

**共有脳について**  
プロセス内で Council が同一 `RustBrain` を保持していてもよいが、**分類入口は必ず `ClassifyOnlyBrain` 経由**とし、`generate()` を呼べない。評議会・マトリョーシカは別エントリポイント（`Council.ask` / matryoshka）。speak は `speak_brain` 論理ハンドル（ClassifyOnly ではない）。
