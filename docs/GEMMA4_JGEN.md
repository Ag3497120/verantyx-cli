# Gemma4 → JGEN (ベクトル異種連携)

目標: Ollama / LM Studio の **API ブリッジではなく**、GGUF を jgen に変換して
0.5B 評議会と **分布インターリンガ / encode_soft** で熟議する。

外部 API 参加者 (`verantyx_bridges.py` の Ollama / LM Studio) は **削除しない**。

## ディスク容量

| 項目 | サイズ | 備考 |
|------|--------|------|
| Ollama GGUF blob (入力) | ~9GB | 既にあるなら追加不要 |
| jgen **PLE あり** (推奨) | **~15.3GB** | `per_layer_token_embd` (~5.6GB) 込み |
| Forge 自動 `--no-ple` 閾値 | 空き **&lt; 20GB** | 安全マージン |
| 推奨空き (新規変換) | **≥ 25GB** | 出力 + 一時 |

```bash
python3 jgen_forge.py pull "gemma-4-abliterated" --name gemma4_e4b_abliterated_ple
# ディスク不足時のみ:
python3 jgen_forge.py pull "gemma-4-abliterated" --name gemma4_e4b_abliterated --no-ple
```

## 成果物

| ファイル | 内容 |
|----------|------|
| `converted_models/gemma4_e4b_abliterated_ple_full.jgen` | 15.25GB, PLE 込み（現行） |

## エンジン実装状況

| 項目 | 状態 |
|------|------|
| Forge gemma4 写像 / lang-only | ✅ |
| Forge gemma4 MoE (EXPS 分割 / router / shared) | ✅ |
| chunked `encode` / `encode_soft` | ✅ |
| 単トークン decode | ✅ |
| logits softcap | ✅ |
| GPU 経路 (Metal/CUDA) | ✅ SWA / shared-KV / GeGLU / PLE / softcap（MoE は CPU フォールバック） |
| 大テンソル u32 オーバーフロー修正 | ✅ |
| **PLE forward** (token + context → gate/proj) | ✅ (E2B/E4B; 26B-A4B は PLE 無し) |
| **MoE forward** (GeGLU experts + shared) | ✅ (26B-A4B; `moe_activation=gelu_pytorch_tanh`) |
| 主埋め込み √hidden スケール | ✅ |

> 旧変換の `.jgen` で `model.layers.*.gguf.ffn_*_exps` になっているものは **再変換必須**。
> MLP 欠落はエラーになる（以前の静かなスキップは廃止）。

GPU は既定で有効 (`JCROSS_GPU=0` で無効化、`JCROSS_DEVICE=cpu` で CPU 強制)。
失敗時は自動で CPU にフォールバック。

### PLE パイプライン (HF Gemma4 準拠)
1. `embed_tokens` × √hidden
2. token-id: `per_layer_token_embd` × √ple_dim → `[L, D]`
3. context: `per_layer_model_proj(h) / √hidden` → reshape → `per_layer_proj_norm`
4. combine: `(ctx + tok) / √2`（soft トークンは context のみ）
5. 各層末尾: `h += post_norm(proj(gelu(gate(h)) ⊙ ple[layer]))`

## スモーク
```bash
JCROSS_DEVICE=cpu python3 -c "
from verantyx_mind import RustBrain
b = RustBrain('converted_models/gemma4_e4b_abliterated_ple_full.jgen')
print(b.hidden, b.num_layers, b.encode([2, 235248, 1754]).shape)
"
```

## API ブリッジ (削除しない)
`verantyx_bridges.py` の `OllamaParticipant` / `LMStudioParticipant` は存続。
