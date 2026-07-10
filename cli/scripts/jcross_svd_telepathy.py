import sys
import os
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForCausalLM

from gemma_trainer import load_gemma_jgen

def load_custom_gemma(device):
    print("[*] Loading Modified Gemma 12B...")
    model_id = "google/gemma-4-12B"
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map=device, low_cpu_mem_usage=True)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        
        base_ckpt = "gemma_12b_trained_step_680.jgen"
        muscle_path = "gemma_12b_muscles_step_900.pt"
        
        if os.path.exists(base_ckpt):
            load_gemma_jgen(model, base_ckpt, device=device)
        if os.path.exists(muscle_path):
            muscles = torch.load(muscle_path, map_location=device)
            for name, param in model.named_parameters():
                if param.requires_grad and name in muscles:
                    param.data.copy_(muscles[name].to(device))
        model.eval()
        for param in model.parameters():
            param.requires_grad = False
        return model, tokenizer
    except Exception as e:
        print(f"[!] Error loading Gemma: {e}")
        return None, None

def load_custom_qwen(device):
    print("[*] Loading Qwen 0.5B...")
    model_id = "Qwen/Qwen1.5-0.5B"
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map=device, low_cpu_mem_usage=True)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model.eval()
        for param in model.parameters():
            param.requires_grad = False
        return model, tokenizer
    except Exception as e:
        print(f"[!] Error loading Qwen: {e}")
        return None, None

def get_anchor_words(gemma_tokenizer, qwen_tokenizer):
    """両方のTokenizerで完全に一致する文字列を持つ単語（アンカー）を抽出"""
    print("[*] Extracting common anchor words between vocabularies...")
    gemma_vocab = gemma_tokenizer.get_vocab()
    qwen_vocab = qwen_tokenizer.get_vocab()
    
    # Gemmaは先頭に " "（SPIECE_UNDERLINE:  ）が付くことが多い。Qwenはプレーンか別のプレフィックス。
    # 簡略化のため、純粋なASCII/Unicode文字列としてマッチするものを探す
    gemma_clean = {k.replace(' ', ''): v for k, v in gemma_vocab.items() if len(k.replace(' ', '')) > 0}
    qwen_clean = {k.decode('utf-8') if isinstance(k, bytes) else k: v for k, v in qwen_vocab.items()}
    
    common_words = set(gemma_clean.keys()).intersection(set(qwen_clean.keys()))
    
    gemma_ids = []
    qwen_ids = []
    # あまりにも一般的な1文字や記号を除外するため、少しフィルタリング
    for word in common_words:
        if len(word) >= 2:
            gemma_ids.append(gemma_clean[word])
            qwen_ids.append(qwen_clean[word])
            
    print(f"[*] Found {len(gemma_ids)} common anchor words (e.g., length >= 2).")
    return torch.tensor(gemma_ids), torch.tensor(qwen_ids)

def run_svd_telepathy():
    device = "cpu"
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    print(f"[*] Using device: {device}")

    gemma_model, gemma_tokenizer = load_custom_gemma(device)
    qwen_model, qwen_tokenizer = load_custom_qwen(device)

    if not gemma_model or not qwen_model:
        print("[!] Models failed to load. Exiting.")
        sys.exit(1)

    print("\\n==================================================")
    print(" [Step 1] Preparing SVD Rotation Matrix")
    print("==================================================")
    
    gemma_ids, qwen_ids = get_anchor_words(gemma_tokenizer, qwen_tokenizer)
    gemma_ids = gemma_ids.to(device)
    qwen_ids = qwen_ids.to(device)
    
    gemma_embeds = gemma_model.get_input_embeddings().weight[gemma_ids].to(torch.float32) # [N, 3840]
    qwen_embeds = qwen_model.get_input_embeddings().weight[qwen_ids].to(torch.float32)    # [N, 1024]
    
    # 中心化 (Mean centering)
    gemma_embeds -= gemma_embeds.mean(dim=0, keepdim=True)
    qwen_embeds -= qwen_embeds.mean(dim=0, keepdim=True)
    
    # 正規化 (L2 normalization for cosine similarity alignment)
    gemma_embeds = F.normalize(gemma_embeds, p=2, dim=-1)
    qwen_embeds = F.normalize(qwen_embeds, p=2, dim=-1)

    print("[*] Calculating SVD (Orthogonal Procrustes)...")
    M = torch.matmul(gemma_embeds.T, qwen_embeds) # [3840, 1024]
    
    # MPS上でsvdが未サポートの場合があるためCPUで計算
    M_cpu = M.cpu()
    U, S, Vh = torch.linalg.svd(M_cpu, full_matrices=False)
    # U: [3840, 1024], Vh: [1024, 1024]
    W = torch.matmul(U, Vh).to(device) # [3840, 1024]
    print(f"[*] Calculated Optimal Rotation Matrix W of shape {W.shape}")

    print("\\n==================================================")
    print(" [Step 2] Zero-Shot Telepathy Testing (Nearest Neighbor)")
    print("==================================================")
    
    test_prompts = [
        "Swiftで書かれたAPIをRustで書き直してください。",
        "人工知能は今後どのように進化していくと思いますか？",
        "Pythonの辞書をループで処理する方法"
    ]
    
    qwen_all_embeds = qwen_model.get_input_embeddings().weight.to(torch.float32) # [VocabSize, 1024]
    qwen_all_embeds = F.normalize(qwen_all_embeds, p=2, dim=-1)

    for text in test_prompts:
        print(f"\\n[Source Thought] (Gemma): '{text}'")
        
        gemma_inputs = gemma_tokenizer(text, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = gemma_model(**gemma_inputs, output_hidden_states=True)
            # 最後の層のHidden Statesを取得 [1, SeqLen, 3840]
            hidden = outputs.hidden_states[-1][0].to(torch.float32)
            
            # SVDによる空間回転 [SeqLen, 1024]
            rotated_hidden = torch.matmul(hidden, W)
            rotated_hidden = F.normalize(rotated_hidden, p=2, dim=-1)
            
            # コサイン類似度によるNearest Neighbor検索
            # rotated_hidden: [SeqLen, 1024], qwen_all_embeds: [Vocab, 1024]
            similarities = torch.matmul(rotated_hidden, qwen_all_embeds.T) # [SeqLen, Vocab]
            
            top_k = 3
            best_token_ids = similarities.argmax(dim=-1) # [SeqLen]
            
            decoded_words = []
            for i, token_id in enumerate(best_token_ids):
                word = qwen_tokenizer.decode([token_id.item()])
                decoded_words.append(word.strip())
                
            print(f"[Direct Mapping] (Qwen) : {' '.join([w for w in decoded_words if w])}")
            
if __name__ == "__main__":
    run_svd_telepathy()
