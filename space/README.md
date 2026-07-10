---
title: Verantyx God Mode
emoji: 💠
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: 0.5B×5役割のベクトル評議会 — 思考が見えるAI
---

# Verantyx God Mode — 思考が見えるAI

**テキストを1トークンも生成せずに議論する** Qwen 0.5B の評議会デモ。

同じ 0.5B の重みから Commander / Scout×2 / Worker×2 の5役割を実フォワードで走らせ、
最終隠れ状態 (1024次元の思考ベクトル) を直接集約します。合意ベクトルは
「仮想トークン」として次のフォワードに注入され (ベクトル通信)、収束すると
対抗馬を混ぜた偽合意を注入する **摂動テスト** で頑健さを検査します。

画面の 3D シーンは各役割の思考ベクトルを PCA で投影したもので、
線とパルスがベクトル注入、レーダーが合意の6概念軸 (実測)、
バーが意見の一致度 (cos) と不確実性 (entropy) を表します。

- 推論エンジン: 自作 Rust エンジン (JGEN v3 形式 / mmap / candle CPU)
- モデル: Qwen2.5-0.5B-Instruct (GGUF q8_0 → JGEN dense 変換、ビルド時に自動)
- 比較のため同じ 0.5B の単独回答も並べて表示します (誇張なし)

フル版 (エスカレーション 9B/35B・永遠の記憶・エージェント・LM Studio/Ollama 連携) は
[GitHub: Ag3497120/verantyx-cli](https://github.com/Ag3497120/verantyx-cli) を参照。
