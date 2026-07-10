import sys
import os
import torch
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
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

    gemma_dim = gemma_model.config.hidden_size if hasattr(gemma_model.config, "hidden_size") else (gemma_model.config.d_model if hasattr(gemma_model.config, "d_model") else 3840)
    try:
        qwen_dim = qwen_model.get_input_embeddings().weight.shape[1]
    except:
        qwen_dim = 1024
        
    jcross_dim = 4096
    target_qwen_seq_len = 16

    router = JCrossTelepathyRouter(gemma_dim, jcross_dim, qwen_dim, target_qwen_seq_len).to(device)
    router = router.to(torch.float32)
    
    # 高解像度化：過学習テスト（1つの概念を極限まで完璧にアライメントする）
    text = "Swiftで書かれたAPIをRustで書き直してください。"
    
    print(f"\\n[*] Starting High-Resolution Alignment Training...")
    print(f"[*] Target Concept: '{text}'")
    
    # Gemma側での推論は1回で済む（固定キャッシュ）
    gemma_inputs = gemma_tokenizer(text, return_tensors="pt").to(device)
    with torch.no_grad():
        gemma_outputs = gemma_model(**gemma_inputs, output_hidden_states=True)
        gemma_hidden = gemma_outputs.hidden_states[-1].to(torch.float32)
        
    qwen_target_inputs = qwen_tokenizer(text, return_tensors="pt").to(device)
    target_ids = qwen_target_inputs.input_ids
    with torch.no_grad():
        target_embeds = qwen_model.get_input_embeddings()(target_ids)

    epochs = 200
    optimizer = AdamW(router.parameters(), lr=3e-4)
    # 学習率スケジューラ：100エポックかけて徐々に下げる
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    
    # Training Loop
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        # --- Router ---
        qwen_soft_prompts, _ = router(gemma_hidden)
        qwen_soft_prompts_bf16 = qwen_soft_prompts.to(qwen_model.dtype)

        # --- Qwen ---
        full_embeds = torch.cat([qwen_soft_prompts_bf16, target_embeds[:, :-1, :]], dim=1)
        outputs = qwen_model(inputs_embeds=full_embeds)
        logits = outputs.logits
        
        logits = torch.nan_to_num(logits, nan=0.0, posinf=1e4, neginf=-1e4)

        shift_logits = logits[0, target_qwen_seq_len-1:, :].contiguous()
        shift_labels = target_ids[0].contiguous()
        
        min_len = min(shift_logits.shape[0], shift_labels.shape[0])
        shift_logits = shift_logits[:min_len]
        shift_labels = shift_labels[:min_len]
        
        loss = F.cross_entropy(shift_logits, shift_labels)
        
        loss.backward()
        torch.nn.utils.clip_grad_norm_(router.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()
        
        if (epoch + 1) % 10 == 0:
            print(f"  [Epoch {epoch+1:3d}/{epochs}] Loss: {loss.item():.6f} | LR: {scheduler.get_last_lr()[0]:.2e}")

    print("\\n[*] Training Complete. Testing Perfect Decoding...")
    
    with torch.no_grad():
        qwen_soft_prompts, _ = router(gemma_hidden)
        qwen_soft_prompts_bf16 = qwen_soft_prompts.to(qwen_model.dtype)
        
        generated_ids = qwen_model.generate(
            inputs_embeds=qwen_soft_prompts_bf16,
            max_new_tokens=20,
            temperature=0.0, # 貪欲法で最も確率が高いものを選択
            do_sample=False,
            pad_token_id=qwen_tokenizer.eos_token_id
        )
    
    decoded_text = qwen_tokenizer.decode(generated_ids[0], skip_special_tokens=True)
    
    print("\\n==================================================")
    print(" [High-Res Telepathy Decoding Result]")
    print("==================================================")
    print(f" Original Concept (Gemma) : {text}")
    print(f" Generated Text (Qwen)    : {decoded_text}")
    print("==================================================")
    
    if text.strip() == decoded_text.strip():
        print(" [SUCCESS] Perfect 1:1 Concept Translation Achieved!")
    else:
        print(" [NOTE] Partial Translation.")
        
    torch.save(router.state_dict(), "jcross_telepathy_router_high_res.pt")
    print("[*] Router weights saved to 'jcross_telepathy_router_high_res.pt'")

if __name__ == "__main__":
    train()
