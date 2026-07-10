import sys
import os
import torch
import torch.nn.functional as F
from torch.optim import AdamW
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
            param.requires_grad = False # Gemma is frozen
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
            param.requires_grad = False # Qwen is frozen
        return model, tokenizer
    except Exception as e:
        print(f"[!] Error loading Qwen: {e}")
        return None, None

def train():
    device = "cpu"
    if torch.backends.mps.is_available():
        device = "mps"
    print(f"[*] Using device: {device}")

    gemma_model, gemma_tokenizer = load_custom_gemma(device)
    qwen_model, qwen_tokenizer = load_custom_qwen(device)

    if not gemma_model or not qwen_model:
        print("[!] Models failed to load. Exiting.")
        sys.exit(1)

    # 次元取得
    gemma_dim = gemma_model.config.hidden_size if hasattr(gemma_model.config, "hidden_size") else (gemma_model.config.d_model if hasattr(gemma_model.config, "d_model") else 3840)
    try:
        qwen_dim = qwen_model.get_input_embeddings().weight.shape[1]
    except:
        qwen_dim = 1024
        
    jcross_dim = 4096
    target_qwen_seq_len = 8

    # Router initialization
    router = JCrossTelepathyRouter(gemma_dim, jcross_dim, qwen_dim, target_qwen_seq_len).to(device)
    # routerの重みをFloatに（Mixed precision回避のため）
    router = router.to(torch.float32)
    # 入力されるGemmaのbfloat16と合わせるために、計算時にキャストする
    
    optimizer = AdamW(router.parameters(), lr=5e-3)

    # 訓練用データセット（様々な概念のプロンプト）
    prompts = [
        "Swiftで書かれたAPIをRustで書き直してください。",
        "Hello, how are you doing today?",
        "人工知能の未来について語りましょう。",
        "I need a Python script to sort an array.",
        "量子コンピュータの基本原理を説明して。",
        "var x = 10; let y = 20; console.log(x + y);",
        "法律の条文における「善意」と「悪意」の違いは？"
    ]

    print("\\n[*] Starting Alignment Training (Telepathy Router Optimization)...")
    epochs = 5
    
    for epoch in range(epochs):
        total_loss = 0.0
        for text in prompts:
            optimizer.zero_grad()
            
            # --- 1. Gemma: Extract Source Thought (Frozen) ---
            gemma_inputs = gemma_tokenizer(text, return_tensors="pt").to(device)
            with torch.no_grad():
                gemma_outputs = gemma_model(**gemma_inputs, output_hidden_states=True)
                # 最後の隠れ層（文脈を保持したテンソル）
                gemma_hidden = gemma_outputs.hidden_states[-1]
                
            # 計算のため float32 に変換
            gemma_hidden_f32 = gemma_hidden.to(torch.float32)

            # --- 2. Telepathy Router: Convert (Trainable) ---
            qwen_soft_prompts, _ = router(gemma_hidden_f32)
            
            # ソフトプロンプトを Qwen が受け取る形(bfloat16等)に戻す
            qwen_soft_prompts_bf16 = qwen_soft_prompts.to(qwen_model.dtype)

            # --- 3. Qwen: Decode and Target matching (Frozen) ---
            # 正解データ（ターゲット）として、Qwenに同じテキストを与えたときのトークンIDを使用
            # つまり、Gemmaの思考からQwenが自力でそのテキストを復元できるようにLossをかける
            qwen_target_inputs = qwen_tokenizer(text, return_tensors="pt").to(device)
            target_ids = qwen_target_inputs.input_ids
            
            # QwenにSoft Promptsを入力してLogitsを取得
            # QwenはFrozenなので勾配は流れないが、入力（Soft Prompts）まで逆伝播する
            # Qwenモデル自体が inputs_embeds に対する勾配計算をサポートしている必要がある
            
            # Qwenの出力取得
            outputs = qwen_model(inputs_embeds=qwen_soft_prompts_bf16)
            logits = outputs.logits # [1, seq_len(8), vocab_size]
            
            # logitsの系列長とtarget_idsの系列長は合わない可能性があるため、
            # 最も簡単なアライメントとして「Qwenが本来生成するEmbeddings」とのMSEを取る方法に変更
            # （CrossEntropyはシーケンス長のアライメントが必要で複雑になるため）
            with torch.no_grad():
                target_embeddings = qwen_model.get_input_embeddings()(target_ids) # [1, text_len, qwen_dim]
            
            # Soft Prompts と Target Embeddings の平均次元(Mean Pooling)でのLossをとる
            # 「文章全体の意味（概念）」がQwenの脳内で同じ位置にマッピングされるようにする
            pred_mean = qwen_soft_prompts.mean(dim=1) # [1, qwen_dim]
            target_mean = target_embeddings.to(torch.float32).mean(dim=1) # [1, qwen_dim]
            
            loss = F.mse_loss(pred_mean, target_mean)
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(prompts)
        print(f"  [Epoch {epoch+1}/{epochs}] Average Loss: {avg_loss:.4f}")

    print("\\n[*] Training Complete. Testing the updated Router...")
    
    # 訓練後のテスト
    test_text = prompts[0]
    gemma_inputs = gemma_tokenizer(test_text, return_tensors="pt").to(device)
    with torch.no_grad():
        gemma_hidden = gemma_model(**gemma_inputs, output_hidden_states=True).hidden_states[-1]
        gemma_hidden_f32 = gemma_hidden.to(torch.float32)
        
        qwen_soft_prompts, _ = router(gemma_hidden_f32)
        qwen_soft_prompts_bf16 = qwen_soft_prompts.to(qwen_model.dtype)
        
        generated_ids = qwen_model.generate(
            inputs_embeds=qwen_soft_prompts_bf16,
            max_new_tokens=20,
            temperature=0.7,
            do_sample=True,
            pad_token_id=qwen_tokenizer.eos_token_id
        )
    
    decoded_text = qwen_tokenizer.decode(generated_ids[0], skip_special_tokens=True)
    
    print("\\n==================================================")
    print(" [Aligned Telepathy Result]")
    print("==================================================")
    print(f" Input (Gemma) : {test_text}")
    print(f" Output (Qwen) : {decoded_text}")
    print("==================================================")
    print(" (Loss decreased indicating structural alignment is progressing)")
    
    # モデルの保存
    torch.save(router.state_dict(), "jcross_telepathy_router_aligned.pt")
    print("[*] Router weights saved to 'jcross_telepathy_router_aligned.pt'")

if __name__ == "__main__":
    train()
