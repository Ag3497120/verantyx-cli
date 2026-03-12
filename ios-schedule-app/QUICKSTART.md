# クイックスタート - 3分で動作確認

最速でアプリを動かす手順です。

## ステップ1: Xcodeプロジェクトを作成（1分）

1. Xcodeを起動 → **「Create a new Xcode project」**
2. **iOS** → **App** → Next
3. 設定を入力：
   - Product Name: `ScheduleApp`
   - Interface: **SwiftUI** ⚠️重要
   - Language: **Swift**
4. Next → 保存場所を選択 → Create

## ステップ2: ファイルを追加（1分）

1. Xcodeの左側で `ContentView.swift` を削除（ゴミ箱アイコン）
2. `ScheduleApp` フォルダを右クリック → **「Add Files to "ScheduleApp"」**
3. 以下のパスに移動：
   ```
   /Users/motonishikoudai/verantyx_v6/ios-schedule-app/ScheduleApp/
   ```
4. **全ての.swiftファイル**を選択（⌘+A）
5. **「Copy items if needed」にチェック** → Add

## ステップ3: 実行（30秒）

1. 上部のシミュレータで **「iPhone 14」** を選択
2. **⌘ + R** を押す
3. アプリが起動！

## 確認すること

✅ カレンダーが表示される
✅ 3件のサンプルスケジュールが表示される
✅ 右上の「+」ボタンをタップ → スケジュールを追加できる
✅ スケジュールをタップ → 詳細が表示される
✅ 左側の○をタップ → 完了チェックができる

## トラブル時

**ビルドエラーが出る**
→ `Product` → `Clean Build Folder` (⇧⌘K) → 再度⌘+R

**アプリが真っ白**
→ シミュレータを再起動 → 再度⌘+R

---

詳細は `SETUP_GUIDE.md` を参照してください。
