import sys
import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from gemma_trainer import load_gemma_jgen
from jcross_telepathy_router import JCrossTelepathyRouter

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
    print("[*] Loading Modified Qwen 0.5B...")
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

def test_telepathy():
    device = "cpu"
    if torch.backends.mps.is_available():
        device = "mps"
    print(f"[*] Using device: {device}")

    gemma_model, gemma_tokenizer = load_custom_gemma(device)
    qwen_model, qwen_tokenizer = load_custom_qwen(device)

    if not gemma_model or not qwen_model:
        print("[!] Models failed to load. Exiting.")
        sys.exit(1)

    gemma_dim = gemma_model.config.hidden_size if hasattr(gemma_model.config, "hidden_size") else (gemma_model.config.d_model if hasattr(gemma_model.config, "d_model") else 3840)
    try:
        qwen_dim = qwen_model.get_input_embeddings().weight.shape[1]
    except:
        qwen_dim = 1024
        
    jcross_dim = 4096
    target_qwen_seq_len = 16

    router = JCrossTelepathyRouter(gemma_dim, jcross_dim, qwen_dim, target_qwen_seq_len).to(device)
    router = router.to(torch.float32)
    
    # 学習済みの汎用ルーターをロード
    ckpt_path = "jcross_telepathy_router_general_epoch3.pt"
    if os.path.exists(ckpt_path):
        print(f"[*] Loading General Telepathy Router weights from {ckpt_path}...")
        router.load_state_dict(torch.load(ckpt_path, map_location=device))
    else:
        print(f"[!] Checkpoint {ckpt_path} not found. Using untrained weights.")

    router.eval()

    # テスト用プロンプト（未知の概念や、学習データに似た概念）
    test_prompts = [
        "Pythonでリストを逆順にする関数を書いてください。",
        "宇宙の起源について、ビッグバン理論を中心に簡単に教えて。",
        "美味しいコーヒーの淹れ方のコツは何ですか？"
    ]

    print("\\n==================================================")
    print(" [General Telepathy Testing Phase]")
    print("==================================================")

    for text in test_prompts:
        print(f"\\n[*] Transmitting Concept: '{text}'")
        
        # --- Gemma: Extract Source Thought ---
        gemma_inputs = gemma_tokenizer(text, return_tensors="pt").to(device)
        with torch.no_grad():
            gemma_outputs = gemma_model(**gemma_inputs, output_hidden_states=True)
            gemma_hidden = gemma_outputs.hidden_states[-1].to(torch.float32)

        # --- Router: Apply General Cross Attention ---
        with torch.no_grad():
            qwen_soft_prompts, _ = router(gemma_hidden)
            # 異常値のクリッピング（NaNやInfによる生成エラーを防ぐ）
            qwen_soft_prompts = torch.nan_to_num(qwen_soft_prompts, nan=0.0, posinf=10.0, neginf=-10.0)
            qwen_soft_prompts = torch.clamp(qwen_soft_prompts, min=-50.0, max=50.0)
            qwen_soft_prompts_bf16 = qwen_soft_prompts.to(qwen_model.dtype)

        # --- Qwen: Decode (Generate text based ONLY on Gemma's thought) ---
        with torch.no_grad():
            generated_ids = qwen_model.generate(
                inputs_embeds=qwen_soft_prompts_bf16,
                max_new_tokens=30,
                temperature=0.0, # Greedy searchで安定化
                do_sample=False,
                pad_token_id=qwen_tokenizer.eos_token_id
            )
        
        decoded_text = qwen_tokenizer.decode(generated_ids[0], skip_special_tokens=True)
        
        print(f" -> Qwen's Telepathic Output: {decoded_text}")
        print("--------------------------------------------------")

if __name__ == "__main__":
    test_telepathy()
