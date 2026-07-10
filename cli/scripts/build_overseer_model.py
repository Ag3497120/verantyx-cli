import os
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='[*] %(message)s')

MODEL_ID = "Qwen/Qwen1.5-0.5B"
OUTPUT_WEIGHTS = "overseer_mixed_weights.jgen"
OUTPUT_ANCHORS = "overseer_anchors.jgen"

# アンカー用プロンプト定義
COMMANDER_PROMPT = """<|im_start|>system
You are the Overseer Commander. Your task is to act as the absolute leader of the swarm network.
Analyze the user request, break it down into precise logical steps, and convert it into a strictly structured thought vector for the worker nodes. Do not output conversational filler.<|im_end|>
<|im_start|>user
"""

TRANSLATOR_PROMPT = """<|im_start|>system
You are the Overseer Translator. Your task is to eavesdrop on the internal communication network, receive the degraded thought vectors from the workers, and completely reconstruct them into perfectly fluent, natural, and grammatical human language. Fix all gibberish and token errors.<|im_end|>
<|im_start|>user
"""

def compress_weight_svd(weight_tensor, rank):
    """特異値分解(SVD)を用いて重み行列を低ランク近似圧縮する"""
    # weight_tensor: [out_features, in_features]
    device = weight_tensor.device
    dtype = weight_tensor.dtype
    
    # MPS環境でsvdが落ちる問題を防ぐためCPU/float32で計算
    W_cpu = weight_tensor.float().cpu()
    U, S, Vh = torch.linalg.svd(W_cpu, full_matrices=False)
    
    # ランクの切り詰め
    U_k = U[:, :rank]
    S_k = S[:rank]
    Vh_k = Vh[:rank, :]
    
    # 復元せず、2つの直交する小さな行列（AとB）に物理的に分割して返す
    # A * B の積が元の重み W に近似する
    S_k_sqrt = torch.sqrt(S_k)
    A = U_k * S_k_sqrt.unsqueeze(0)        # [out_features, rank]
    B = S_k_sqrt.unsqueeze(1) * Vh_k       # [rank, in_features]
    
    return {
        "jcross_A": A.to(dtype=dtype, device=device),
        "jcross_B": B.to(dtype=dtype, device=device)
    }

def main():
    device = "cpu"
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"

    logging.info(f"Loading Base Model ({MODEL_ID}) to {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, 
        torch_dtype=torch.float16, 
        low_cpu_mem_usage=True
    ).to(device)

    # 1. 認知アンカー（Cognitive Anchors）の生成
    logging.info("Generating Cognitive Anchors (Dual-Persona)...")
    embed_layer = model.get_input_embeddings()
    
    # Commander アンカー
    cmd_inputs = tokenizer(COMMANDER_PROMPT, return_tensors="pt").to(device)
    cmd_anchor = embed_layer(cmd_inputs.input_ids).detach().cpu()
    
    # Translator アンカー
    trans_inputs = tokenizer(TRANSLATOR_PROMPT, return_tensors="pt").to(device)
    trans_anchor = embed_layer(trans_inputs.input_ids).detach().cpu()
    
    anchors = {
        "commander": cmd_anchor,
        "translator": trans_anchor
    }
    torch.save(anchors, OUTPUT_ANCHORS)
    logging.info(f"Saved Cognitive Anchors to {OUTPUT_ANCHORS}")

    # 2. 知識と通信の分離（混合ランク SVD 圧縮）
    logging.info("Applying Mixed-Rank SVD Compression (JCross Topology)...")
    
    compressed_state_dict = {}
    
    # 全パラメータを走査
    total_layers = len(model.model.layers)
    for name, param in model.named_parameters():
        # EmbeddingやLayerNorm等はそのまま保持
        if "embed_tokens" in name or "norm" in name or "lm_head" in name:
            compressed_state_dict[name] = param.detach().cpu()
            continue
            
            # 線形層（Linear）に対する処理
        if "proj" in name or "fc" in name:
            if param.dim() < 2:
                # バイアス項など1次元のものは圧縮せずそのまま保持
                compressed_state_dict[name] = param.detach().cpu()
                continue
                
            # 層のインデックスを取得
            layer_idx = -1
            if "layers." in name:
                try:
                    layer_idx = int(name.split("layers.")[1].split(".")[0])
                except ValueError:
                    pass

            # 通信空間 (Layer 0 の q_proj, k_proj 等): Rank = 256
            if layer_idx == 0:
                rank = 256
                logging.info(f"  [Communication Space] Compressing {name} with Rank={rank} (High Fidelity)")
            # 知識空間 (Layer > 0 の全ての層、または MLP): Rank = 128
            else:
                rank = 128
                logging.info(f"  [Knowledge Space] Compressing {name} with Rank={rank} (High Compression)")

            # 特異値分解による圧縮と物理的分割（True JCross Topology）
            jcross_matrices = compress_weight_svd(param.detach(), rank=rank)
            
            # 元の .weight という名前を消し、2つの小さなキーとして登録
            base_name = name.replace(".weight", "")
            compressed_state_dict[f"{base_name}.jcross_A"] = jcross_matrices["jcross_A"].cpu()
            compressed_state_dict[f"{base_name}.jcross_B"] = jcross_matrices["jcross_B"].cpu()
        else:
            compressed_state_dict[name] = param.detach().cpu()

    # 3. 改造モデルの保存
    logging.info(f"Saving Overseer Mixed-Rank Weights to {OUTPUT_WEIGHTS}...")
    torch.save(compressed_state_dict, OUTPUT_WEIGHTS)
    
    logging.info("Overseer Model Build Complete!")

if __name__ == "__main__":
    main()
