# Capture ↔ Verantyx 同期 (v1)

合意日: 2026-07-12

## 分業

| 側 | 担当 |
|----|------|
| **Capture** (`open-object-house`) | UI・操作・LiDAR/手・InteractionRecord 収録・Export・Play 用 `scene.json` |
| **Verantyx** (本リポジトリ) | `interactions` インポート → SpatialEpisode / JCross スロット、空間操作コア、Locate / Return / Relation 評価 |

- LLM は言語入口のみ。部屋データでのフル FT はしない。
- v1 では落下物理・自動命名・写真級メッシュは約束しない。
- 落下は `actionLabel=drop` + `userCorrection.kind=drop` のログのみ。

## Capture Export レイアウト (受信契約)

```text
Documents/OpenObjectHouseCapture/<timestamp>/
  Manifest/scene.json
  Manifest/containers.json
  interactions/<id>.json
  interactions/all.json
  interactions/index.json
  Rooms|Objects の粗い usda/obj
```

スキーマ準拠サンプル（Capture 手渡し・本リポにコピー済）:

```text
benchmarks/datasets/sample_room_v1/
# 原本: open-object-house/Samples/VerantyxHandoff/OpenObjectHouseCapture/sample_room_v1/
```

InteractionRecord / scene で吸収済みの差分:

- `id` (= recordID), `actionLabel`: lift / drop / extract / **restore** (= return)
- pose: `position: [x,y,z]` + **`rotationYDegrees`**（quat も可）
- trajectory: `position` または `objectPosition`
- `containers.json`: **配列** `[{id, childObjectIDs, ...}]`
- `scene.json` objects: `id` / `displayName` / `contents` / `state.clusterParent`
- drop: `userCorrection.kind=drop`（`correctedAt` 可）

InteractionRecord 必須寄りフィールド:

- `objectID`, `roomID`, `containerID?`
- `poseHome`, `poseBefore`, `poseAfter`
- `actionLabel`, `motionTrajectory`, `handSamples?`, `userCorrection?`

## Verantyx 実装エントリ

| ファイル | 役割 |
|----------|------|
| [`spatial_episode.py`](../spatial_episode.py) | インポート・SpatialEpisode・SpatialStore・短い指示パース |
| [`benchmarks/spatial_ops_bench.py`](../benchmarks/spatial_ops_bench.py) | Locate / Return / Relation 最小ベンチ |
| [`benchmarks/datasets/sample_room_v1/`](../benchmarks/datasets/sample_room_v1/) | Capture 手渡しサンプル |
| Omni `/spatial` | ingest / status / locate / 戻して |

実機パッケージが来たら:

```bash
python3 spatial_episode.py ingest /path/to/OpenObjectHouseCapture/<timestamp>
python3 spatial_episode.py ask "Blue Mug はどこ"
# または Omni 内: /spatial ingest …  /spatial Blue Mug はどこ
```

## v1 共通ゴール

登録区画で「どこ？／出して／戻して」が、登録物 + poseHome + 関係つきで回り、save/load できること。

Flat vs Graph vs JCross の形式比較は、実機データが溜まってから。
