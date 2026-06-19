<div align="center">
  <h1>🛡️ Verantyx (Verifiable & Auditable AI Engine)</h1>
  <p><b>The Zero-Leakage, Neuro-Symbolic AI Coding Gateway & Native macOS IDE</b></p>

  <p>
    <a href="https://github.com/verantyx/verantyx/releases/latest"><img src="https://img.shields.io/badge/version-1.4.0-blue?style=flat-square" alt="Version 1.4.0"></a>
    <img src="https://img.shields.io/badge/platform-macOS%2014%2B-lightgrey?style=flat-square">
    <img src="https://img.shields.io/badge/Apple%20Silicon-optimized-orange?style=flat-square">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square">
  </p>
  <p>
    <a href="README-en.md">English</a> · <a href="README-es.md">Español</a> · <a href="README-pt-BR.md">Português (Brasil)</a> · <a href="README-de.md">Deutsch</a> · <a href="README-fr.md">Français</a> · <a href="README-zh-CN.md">简体中文</a> · <a href="README-zh-TW.md">繁體中文</a> · <a href="README-ko.md">한국어</a> · <a href="README.md">日本語</a> · <a href="README-ar.md">العربية</a> · <a href="README-ru.md">Русский</a> · <a href="README-uk.md">Українська</a> · <a href="README-tr.md">Türkçe</a>
  </p>
</div>

---

Verantyxは、AIによるソフトウェア開発を完全に制御可能で安全なものにするための、次世代のNeuro-Symbolicロジックエンジンです。
私たちは、1つの強力なコアエンジン（JCross/L3.5 Memory）の上に、**2つの異なるフロントエンド**を提供しています。あなたの目的に合わせて選択してください。

---

## 1. 🖥️ Verantyx Gatekeeper (IDE Mode)
**「会社の機密コードを、安全にクラウドLLMに読ませたい」**

Gatekeeperモードは、あなたのソースコードを意味を持たない数学的パズル（Opaque Topology）に難読化してからAIに渡す、究極のセキュアIDEです。
👉 [Gatekeeperモードの詳細と難読化の仕組み（README-Gatekeeper.md）はこちら](./docs/README-Gatekeeper.md)

## 2. ⚡ Verantyx Agent (Spotlight Mode)
**「最強のローカルAIを、脳の拡張として完全に使いこなしたい」**

`Control`キーを3回押すだけで起動する、超自律型のエージェントです。Dual Twinによる内部監査、1930年メタファによるハルシネーションの物理遮断、そしてPCの資産を「自分の記憶（L3.5）」として認識する次世代の思考エンジンを搭載しています。
👉 [Agentモードの詳細とアーキテクチャ（README-Agent.md）はこちら](./docs/README-Agent.md)

## 3. 🥽 Verantyx VR Bridge (PCVR Streaming)
**「MacでHalf-Life: Alyxを動かし、Vision Proで遊ぶ」**

Verantyxの新たなサブプロジェクトとして、MacのD3DMetal(GPTK)上で動くSteamVRゲームを直接Apple Vision Proへストリーミングする超低遅延VRブリッジ機能が追加されました。
- **Mac側 (HardwareEncoder)**: 独自のOpenVRエミュレータ（`openvr_emulator.cpp`）がゲームエンジン(Source 2)からDirectX 11のテクスチャを横取りし、macOSのVideoToolboxを用いてHEVC (H.265) ハードウェアエンコードを実行。UDPでVision Proへ直接送信します。
- **入力マッピング**: Joy-Conなどのゲームパッド入力をPythonスクリプト(`joycon_mapper.py`)で仮想VRコントローラーに変換し、ゲームにフィードバックします。
👉 現在、Vision Pro上で平面への描画（2Dウィンドウ）まで成功しており、今後はCompositorServices (Metal) を用いた完全なフルイマーシブVR対応を目指しています。

---

## 💻 インストール方法 (ソースからのビルド)

**必須要件:**
- macOS 14.0以降 (Apple Siliconを強く推奨)
- Xcode 15.0以降

```bash
git clone https://github.com/Ag3497120/Verantyx.git
cd Verantyx/cli/VerantyxIDE
open Verantyx.xcodeproj
# Verantyxのスキームを選択し、Cmd+Rを押してビルド・実行します
```

*注意: Windows / Linuxへの移植（Rustコア + llama.cpp）は長期的なロードマップにありますが、現在はネイティブなmacOS / MLXアーキテクチャの完成に極度に注力しています。*

---

## 📖 Verantyx について

このプロジェクトは以前ルールベースのシンボリックAIを作成しようとしていた際に個人では作るのは不可能であると思い、現在主流のAIのハーネスの部分など制御する部分を自作することで制御しようと考えました。（当時はopenclawが注目を集めていた時期）
そこからこのプロジェクトの主目的である、クラウドの高性能なAIに渡す前にソースコードやユーザーのリクエストを難読化してパズルのような状態にして渡すことで情報漏洩を防げるのではないかと思い開発を始めました。

このプロジェクトがスター0な理由について、このプロジェクトでセキュアなフォルダが含まれていたため急遽プライベートリポジトリにしたため、9あったスターが消滅しました。完全に復活しましたのでよろしくお願いします。そのほかのリポジトリと重複を起こしているような部分を整理しました。このリポジトリにおいてリリースを中心にプッシュしていましたが、ソースコードの更新が滞っていたのを見つけて更新しました。

これからは母国語である日本語を主力にして、英語は通常の翻訳ツールに翻訳させて一応載せるという運用で行こうと考えています。

---

## 🔧 リポジトリの設定と履歴について

**Git設定に関するお知らせ:**
このリポジトリの初期のコミットは、開発者のmacOSのユーザー名に由来する `kofdai` というローカルのGit名で行われていました。2026年5月24日をもってこの問題は修正され、現在すべてのコミットは正しく `@Ag3497120` に帰属するように設定されています。これは開発環境のセットアップにおける一般的な問題であり、ボットや自動化ツールによるものではありません。今後のすべての貢献は正しい作者名で記録されます。

---

## 🚀 How to Run Swarm Pipeline (CLI)

You can launch the highly autonomous Swarm Pipeline directly from the terminal. The system automatically scales the number of agents and the complexity of the Discussion Layer based on your physical memory allocation to prevent Out-of-Memory (OOM) errors.

### Usage (Important Note on Directory)
The Swift Package definition (`Package.swift`) is located inside the `cli/` directory. **You must run the command from inside the `cli/` directory or explicitly specify the package path.** If you run it from the root directory without specifying the path, you will get a `Could not find Package.swift in this directory` error.

**Option A: Standard Terminal Execution**
```bash
cd cli
swift run verantyx-cli swarm "Your prompt here" --memory <size>
```

**Option B: One-liner / AI Agent Execution**
If you are automating this via an AI agent or a script where the working directory might reset, use the `--package-path` argument to reliably execute it from the repository root:
```bash
swift run --package-path cli verantyx-cli swarm "Your prompt here" --memory <size>
```

### Memory Presets & Scaling

- `--memory 16gb`: **Lightweight Mode** (3 nodes). Skips the discussion layer and runs a fast sequential pipeline (Commander -> Worker -> Final).
- `--memory 24gb`: **Standard Mode** (5 nodes). Similar to 16GB but with 3 workers for handling more steps.
- `--memory 32gb`: **Advanced Mode** (7 nodes). Activates the Discussion Layer (1 SubCommander) to review and fix logic before execution.
- `--memory 64gb` *(Default)*: **Full Swarm Mode** (13 nodes). Unleashes the complete architecture with 3 SubCommanders engaging in deep brainstorming and voting, followed by up to 10 physical worker nodes for execution.

> **Note**: This CLI pipeline operates by transferring native cognitive tensors (`hidden_states`) directly across independent processes via sockets. This true "telepathy" architecture avoids textual degradation and minimizes context generation overhead during agent handoffs.
