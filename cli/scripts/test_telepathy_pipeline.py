import torch
import torch.nn.functional as F
import argparse
import sys
from transformers import AutoTokenizer, AutoModelForCausalLM

from jcross_telepathy_router import JCrossTelepathyRouter

def main():
    parser = argparse.ArgumentParser(description="JCross Telepathy Pipeline Test")
    parser.add_argument("--gemma_model", type=str, default="google/gemma-2b", help="Path or name of the Gemma model (e.g., 12B/9B/2B)")
    parser.add_argument("--qwen_model", type=str, default="Qwen/Qwen2.5-0.5B-Instruct", help="Path or name of the Qwen model (0.5B)")
    parser.add_argument("--text", type=str, default="Hello, how can I use JCross for 3D tensor mapping?", help="Input text for telepathy test")
    args = parser.parse_args()

    # デバイス設定 (Mac Mシリーズの場合はMPS、それ以外はCPU/CUDA)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Using device: {device}")

    # --- 1. モデルのロード ---
    print(f"\\n[*] Loading Gemma Model ({args.gemma_model})...")
    # メモリ制約を考慮してbfloat16またはfloat16でロード
    try:
        gemma_tokenizer = AutoTokenizer.from_pretrained(args.gemma_model)
        gemma_model = AutoModelForCausalLM.from_pretrained(args.gemma_model, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True).to(device)
        gemma_model.eval()
    except Exception as e:
        print(f"[!] Error loading Gemma model: {e}")
        print("    -> Proceeding with dummy Gemma output for pipeline testing...")
        gemma_model = None

    print(f"\\n[*] Loading Qwen Model ({args.qwen_model})...")
    try:
        qwen_tokenizer = AutoTokenizer.from_pretrained(args.qwen_model)
        qwen_model = AutoModelForCausalLM.from_pretrained(args.qwen_model, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True).to(device)
        qwen_model.eval()
    except Exception as e:
        print(f"[!] Error loading Qwen model: {e}")
        print("    -> Cannot proceed without Qwen model.")
        sys.exit(1)

    # --- 2. モデル次元の取得 ---
    if gemma_model is not None:
        gemma_dim = gemma_model.config.hidden_size
    else:
        gemma_dim = 2048 # ダミーの次元
    
    qwen_dim = qwen_model.config.hidden_size
    jcross_dim = 4096
    target_qwen_seq_len = 8 # Qwenに渡すテレパシートークン（Soft Prompts）の数

    print(f"\\n[*] Dimensions - Gemma: {gemma_dim}, Qwen: {qwen_dim}, JCross: {jcross_dim}")

    # --- 3. Telepathy Router の初期化 ---
    print("[*] Initializing JCross Telepathy Router...")
    # bfloat16で初期化
    router = JCrossTelepathyRouter(gemma_dim, jcross_dim, qwen_dim, target_qwen_seq_len).to(device).to(torch.bfloat16)

    # --- 4. 実行パイプライン ---
    print(f"\\n[*] Test Text: '{args.text}'")

    if gemma_model is not None:
        print("[*] Step 1: Processing text through Gemma...")
        gemma_inputs = gemma_tokenizer(args.text, return_tensors="pt").to(device)
        with torch.no_grad():
            # output_hidden_states=True で内部の数値（自然言語になる前の状態）を取得
            gemma_outputs = gemma_model(**gemma_inputs, output_hidden_states=True)
            # 最後の隠れ層の出力を取得: [batch, seq_len, gemma_dim]
            gemma_hidden = gemma_outputs.hidden_states[-1]
    else:
        print("[*] Step 1: Mocking Gemma hidden states...")
        gemma_seq_len = 10
        gemma_hidden = torch.randn(1, gemma_seq_len, gemma_dim, dtype=torch.bfloat16).to(device)
    
    print(f"    -> Gemma Output (Hidden States) Shape: {gemma_hidden.shape}")

    print("\\n[*] Step 2: Translating via JCross Telepathy Router...")
    # Routerを通過させる
    with torch.no_grad():
        qwen_soft_prompts, jcross_energy = router(gemma_hidden)
    
    print(f"    -> JCross Energy State Shape: {jcross_energy.shape}")
    print(f"    -> Qwen Telepathy Prompts Shape: {qwen_soft_prompts.shape}")

    print("\\n[*] Step 3: Injecting translated numerical data into Qwen...")
    # Qwen側で生成するためのプロンプトとして扱う
    # 通常のテキスト入力をEmbeddings層で変換せず、直接 `inputs_embeds` として注入する
    
    # テストとして、Qwenがこの数値羅列からどのような自然言語を紡ぎ出すか観察する
    with torch.no_grad():
        generated_ids = qwen_model.generate(
            inputs_embeds=qwen_soft_prompts,
            max_new_tokens=20,
            temperature=0.7,
            do_sample=True,
            pad_token_id=qwen_tokenizer.eos_token_id
        )
    
    decoded_text = qwen_tokenizer.decode(generated_ids[0], skip_special_tokens=True)
    
    print("\\n==================================================")
    print(" [Telepathy Result (Pre-Training State)]")
    print("==================================================")
    print(f" Input (Gemma) : {args.text}")
    print(f" Output (Qwen) : {decoded_text}")
    print("==================================================")
    print(" Note: Since the JCross Router is untrained (randomly initialized),")
    print(" the Qwen output will likely be random text or hallucinations.")
    print(" The true test is that the pipeline executes end-to-end without")
    print(" tokenizer mismatches, proving 'telepathy' is mathematically possible.")

if __name__ == "__main__":
    main()
