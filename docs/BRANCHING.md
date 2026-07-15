# ブランチ方針 (`main` / `stable`)

## English (short)

- **`main`**: default development branch — fast, large WIP commits OK (“thinking out loud”).
- **`stable`**: curated snapshots for outsiders — squash-merge from `main` when the author decides the tip is showable.
- **Default branch stays `main`.** Visitors who want a calmer tree should check out **`stable`** or the latest [GitHub Release](https://github.com/Ag3497120/verantyx-cli/releases). Prefer tagging `vX.Y.Z` from `stable`. Full Japanese guide below.

---

## モデル

| ブランチ | 役割 |
|---|---|
| **`main`** | 開発の本線。速い・大きなコミット OK。WIP・試行錯誤が載ってよい。GitHub のデフォルトブランチ。 |
| **`stable`** | 外部向けの**厳選スナップショット**。著者が「見せてよい」と判断したときだけ `main` から取り込む。 |

`release` という名前は使わず、**`stable`** を訪問者向けの落ち着いた先端とする（レガシーな `release_verantyx` 等とは別物）。

## 新規参加者へ

- まずは **`stable`**、または最新の **GitHub Release / タグ**を試す。
- **`main`** は速く動き、履歴が雑に見えることがある。壊れているとは限らないが、デモ・紹介には向かないことがある。
- コントリビュート（機能ブランチ）は通常 **`main` から切る**。

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
git checkout stable    # 落ち着いたスナップショット
# 開発する場合:
git checkout main
git checkout -b fix/your-topic
```

詳細: [`RELEASES.md`](RELEASES.md) · [`CONTRIBUTING.md`](../CONTRIBUTING.md)

## stable スナップショットの切り方

著者が「今の `main` を見せてよい」と判断したときだけ行う。履歴の force-push や rewrite はしない。

### 推奨: squash merge PR (`main` → `stable`)

1. `main` を最新にする（ローカルで確認）。
2. GitHub で **base = `stable`**, **compare = `main`** の PR を開く（または下のスクリプト）。
3. タイトル例: `stable: snapshot YYYY-MM-DD`（または次のセマンティック版）。
4. **Squash and merge** で取り込む（1 コミットにまとまった「見せ用」点になる）。
5. 必要ならそのコミットにタグを打つ（下記）。

### 代替: ローカル `merge --squash`

```bash
git fetch origin
git checkout stable
git pull origin stable
git merge --squash origin/main
git commit -m "stable: snapshot from main ($(date -u +%Y-%m-%d))"
git push origin stable
```

コンフリクトが出たら解消してからコミット。`main` の履歴は書き換えない。

### 補助スクリプト

```bash
./scripts/cut_stable.sh          # 手順を表示
./scripts/cut_stable.sh --pr     # gh で main→stable の PR 下書きを開く
```

## タグ方針

- **推奨:** 製品向けの `vX.Y.Z`（および必要なら `-alpha` / `-beta`）は **`stable` 上のコミット**から打つ。
- `main` 直付けのタグは「開発途中の印」になりうる。外部向けリリースノートは `stable` 基準を優先。
- 既存の古いタグ（Claude-Code 時代など）は考古学用。現行 README と食い違う場合は **現行ドキュメントと `stable` / 最新 Release** を信じる。
- タグや履歴の一括 rewrite はしない。

## デフォルトブランチ

GitHub の default は **`main` のまま**。訪問者向けの案内として `stable` をドキュメントで案内するだけ（default を勝手に切り替えない）。
