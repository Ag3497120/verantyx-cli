# Capture 精度レンジ切替フロー v2（ピンチ廃止）

合意対象: `open-object-house` Capture ↔ Verantyx  
関連契約: [`CAPTURE_SYNC.md`](CAPTURE_SYNC.md)  
実装参照: [`capture_scan_flow.py`](../capture_scan_flow.py)

## 旧フローの失敗点

1. **ピンチで小物モードへ切替** → 物を持ったままもう片方の手でピンチする必要があり、両手操作が潰れる  
2. **本棚から取り出した小物でレンジ未切替** → 部屋スケールのまま精密が落ちる  
3. **小物が背景と一体化** → foreground isolation が無い／弱い  

## 新フロー（要約）

```text
room_full（歩き撮り）
  │  指と物体の接触で掴み判定（ピンチはモード切替に使わない）
  ▼
object_candidate（周囲候補をリング表示）
  │  視線ポインタを候補へ 3 秒 dwell
  ▼
close_range（小物） / large_object（両手・大物）
  │  撮影中は指見つめメニューを Digital Crown までロック
  │  close_range は背景カットアウト必須
  ▼
release → room_full（メニュー解除は Crown）
```

## 判定ルール

| 信号 | 意味 |
|------|------|
| 指先〜メッシュ距離 ≤ 1.8cm が 2 本以上 | 掴み成立 |
| `handsUsed == 2` | `sizeClass=large`（棚・モニタ等） |
| `handsUsed == 1` + AABB / LiDAR | `small` / `medium` |
| LiDAR ≤ 0.55m かつ small/medium | 精密レンジへ寄せる |
| 視線 dwell 3s | 撮影対象確定 + 対応関係（container/relation）記録 |
| 接触指本数（+ 初動加速度 + 指強張り） | `weight.massProxyKg`（相対プロキシ） |

**ピンチは UI ショートカットとして残してもよいが、スキャンモード切替トリガにはしない。**

## InteractionRecord 追加フィールド

```json
"scanCapture": {
  "schemaVersion": 2,
  "mode": "close_range",
  "sizeClass": "small",
  "trigger": "grasp_contact",
  "profile": {
    "mode": "close_range",
    "lidar_focus_m": 0.55,
    "voxel_size_m": 0.004,
    "isolate_foreground": true,
    "max_background_depth_m": 0.75
  },
  "grasp": {
    "handsUsed": 1,
    "contactFingers": ["thumb", "index", "middle"],
    "lidarDistanceM": 0.42,
    "objectExtentM": 0.22,
    "objectAccelMps2": 0.9,
    "tipStiffnessProxy": 0.35,
    "pinchIgnoredForModeSwitch": true
  },
  "weight": {
    "fingerCount": 3,
    "fingers": ["index", "middle", "thumb"],
    "handsUsed": 1,
    "sizeClass": "small",
    "massProxyKg": 0.28,
    "confidence": 0.75
  },
  "gazeConfirmed": true,
  "gazeDwellSec": 3.0,
  "menuLocked": true,
  "isolationApplied": true,
  "selectedObjectID": "book_1",
  "containerID": "shelf_living",
  "relation": "in",
  "candidateIDs": ["book_1", "book_2"]
}
```

## Capture 実装チェックリスト

- [ ] ピンチトグル経路を削除、または no-op 化  
- [ ] 掴み = 指接触（両手カウント付き）  
- [ ] 候補リング + 視線 3s で撮影開始  
- [ ] 小物 `close_range` で `isolate_foreground=true` を強制  
- [ ] 撮影中メニューロック、解除は Digital Crown  
- [ ] `scanCapture` を InteractionRecord に必ず付与して Export  

## Verantyx 側

- `capture_scan_flow.CaptureScanFlow` … 状態機械・不変条件  
- `spatial_episode.InteractionRecord.scan_capture` … 取り込み  
- `SpatialEpisode.meta.scanCapture` / `massProxyKg` … ゲーム化・軽い学習用  
