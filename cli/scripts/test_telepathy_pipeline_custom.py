import sys
import os
import torch
import argparse
from transformers import AutoTokenizer, AutoModelForCausalLM

# gemma_trainer から JGen ロード関数をインポート
from gemma_trainer import load_gemma_jgen
from jcross_telepathy_router import JCrossTelepathyRouter

def load_custom_gemma(device):
    print("\\n[*] Loading Modified Gemma 12B (JCross Enhanced)...")
    model_id = "google/gemma-4-12B"
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map=device, low_cpu_mem_usage=True)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        
        base_ckpt = "gemma_12b_trained_step_680.jgen"
        muscle_path = "gemma_12b_muscles_step_900.pt"
        
        if os.path.exists(base_ckpt):
            print(f"[*] Injecting Base JGEN ({base_ckpt})...")
            load_gemma_jgen(model, base_ckpt, device=device)
        
        if os.path.exists(muscle_path):
            print(f"[*] Injecting Muscle Memory ({muscle_path})...")
            muscles = torch.load(muscle_path, map_location=device)
            for name, param in model.named_parameters():
                if param.requires_grad and name in muscles:
                    param.data.copy_(muscles[name].to(device))
                    
        model.eval()
        return model, tokenizer
    except Exception as e:
        print(f"[!] Error loading Gemma 12B: {e}")
        return None, None

def load_custom_qwen(device):
    print("\\n[*] Loading Modified Qwen 0.5B...")
    model_id = "Qwen/Qwen1.5-0.5B" # ユーザー環境のキャッシュに合わせて変更可
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map=device, low_cpu_mem_usage=True)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        
        # 改造モデル (qwen_0.5b.jcross) が存在する場合は特別なロードが必要だが、
        # ここではまずHFベースモデルとしてロードし、JCrossテレパシーの受信側として待機させる
        model.eval()
        return model, tokenizer
    except Exception as e:
        print(f"[!] Error loading Qwen 0.5B: {e}")
        return None, None

def main():
    parser = argparse.ArgumentParser(description="JCross Telepathy: Modified Gemma 12B -> Qwen 0.5B")
    parser.add_argument("--text", type=str, default="Swiftで書かれたAPIをRustで書き直してください。", help="Input text for telepathy")
    args = parser.parse_args()

    # 12Bモデルは重いため、メモリに余裕があればMPS、無ければCPU
    device = "cpu"
    if torch.backends.mps.is_available():
        # MPSを試すが、OOM回避のために設定によってはCPUにフォールバックする
        device = "mps"
        
    print(f"[*] Using device: {device}")

    # --- 1. 改造モデルのロード ---
    gemma_model, gemma_tokenizer = load_custom_gemma(device)
    qwen_model, qwen_tokenizer = load_custom_qwen(device)

    if not gemma_model or not qwen_model:
        print("[!] Missing required models for telepathy test. Exiting.")
        sys.exit(1)

    # --- 2. パイプライン実行 ---
    print(f"\\n[*] Test Text (Concept to transmit): '{args.text}'")

    print("[*] Step 1: Brain extraction from Gemma 12B...")
    gemma_inputs = gemma_tokenizer(args.text, return_tensors="pt").to(device)
    with torch.no_grad():
        gemma_outputs = gemma_model(**gemma_inputs, output_hidden_states=True)
        gemma_hidden = gemma_outputs.hidden_states[-1] # [batch, seq_len, hidden]

    print(f"    -> Extracted Thought Vector Shape: {gemma_hidden.shape}")
    
    # 隠れ層の実際の出力次元を使用
    gemma_dim = gemma_hidden.shape[-1]
    try:
        qwen_dim = qwen_model.get_input_embeddings().weight.shape[1]
    except Exception:
        qwen_dim = 1024
    jcross_dim = 4096
    target_qwen_seq_len = 8

    print(f"\\n[*] Dimensions - Gemma: {gemma_dim}, Qwen: {qwen_dim}, JCross: {jcross_dim}")

    # --- 3. JCross Telepathy Router の初期化 ---
    print("[*] Initializing JCross Telepathy Router...")
    router = JCrossTelepathyRouter(gemma_dim, jcross_dim, qwen_dim, target_qwen_seq_len).to(device).to(torch.bfloat16)

    print("\\n[*] Step 2: Translating through JCross Space...")
    with torch.no_grad():
        qwen_soft_prompts, jcross_energy = router(gemma_hidden)
    
    print(f"    -> JCross Energy State Shape: {jcross_energy.shape}")
    print(f"    -> Converted Qwen Prompts Shape: {qwen_soft_prompts.shape}")

    print("\\n[*] Step 3: Injecting thought into Qwen 0.5B brain...")
    with torch.no_grad():
        generated_ids = qwen_model.generate(
            inputs_embeds=qwen_soft_prompts,
            max_new_tokens=30,
            temperature=0.7,
            do_sample=True,
            pad_token_id=qwen_tokenizer.eos_token_id
        )
    
    decoded_text = qwen_tokenizer.decode(generated_ids[0], skip_special_tokens=True)
    
    print("\\n==================================================")
    print(" [Telepathy Result]")
    print("==================================================")
    print(f" Concept injected from Gemma : {args.text}")
    print(f" Decoded interpretation by Qwen: {decoded_text}")
    print("==================================================")
    print(" (Note: Router is untrained, so interpretation may be noisy, but the mathematical channel is open.)")

if __name__ == "__main__":
    main()
