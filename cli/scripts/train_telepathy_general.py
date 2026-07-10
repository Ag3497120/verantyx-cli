import sys
import os
import torch
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from transformers import AutoTokenizer, AutoModelForCausalLM
from datasets import load_dataset
from tqdm import tqdm

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

def get_dataset(num_samples=2000):
    print(f"[*] Downloading Instruction Dataset (Dolly 15k JA)...")
    dataset = load_dataset("kunishou/databricks-dolly-15k-ja")
    # 命令(instruction)のみを抽出して利用
    texts = dataset['train']['instruction']
    # 短すぎず長すぎない文を抽出
    filtered_texts = [t for t in texts if 10 < len(t) < 150][:num_samples]
    print(f"[*] Loaded {len(filtered_texts)} prompts for General Telepathy Training.")
    return filtered_texts

def train():
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

    gemma_dim = gemma_model.config.hidden_size if hasattr(gemma_model.config, "hidden_size") else (gemma_model.config.d_model if hasattr(gemma_model.config, "d_model") else 3840)
    try:
        qwen_dim = qwen_model.get_input_embeddings().weight.shape[1]
    except:
        qwen_dim = 1024
        
    jcross_dim = 4096
    target_qwen_seq_len = 16

    router = JCrossTelepathyRouter(gemma_dim, jcross_dim, qwen_dim, target_qwen_seq_len).to(device)
    router = router.to(torch.float32)
    
    # Check if we have pre-aligned weights to start from
    high_res_ckpt = "jcross_telepathy_router_high_res.pt"
    if os.path.exists(high_res_ckpt):
        print(f"[*] Loading pre-trained high-res router weights from {high_res_ckpt}...")
        router.load_state_dict(torch.load(high_res_ckpt, map_location=device))
    
    # データセット取得
    train_texts = get_dataset(num_samples=2000)
    
    epochs = 3
    accumulation_steps = 16
    optimizer = AdamW(router.parameters(), lr=1e-4)
    total_steps = (len(train_texts) // accumulation_steps) * epochs
    scheduler = CosineAnnealingLR(optimizer, T_max=total_steps, eta_min=1e-6)
    
    print("\\n[*] Starting General Telepathy Alignment Training...")
    print(f"[*] Epochs: {epochs}, Data Size: {len(train_texts)}, Acc Steps: {accumulation_steps}")
    
    global_step = 0
    for epoch in range(epochs):
        print(f"\\n--- Epoch {epoch+1}/{epochs} ---")
        optimizer.zero_grad()
        epoch_loss = 0.0
        
        # tqdmで進捗バーを表示
        pbar = tqdm(train_texts, desc=f"Epoch {epoch+1}")
        
        for i, text in enumerate(pbar):
            # --- Gemma: Extract Source Thought ---
            gemma_inputs = gemma_tokenizer(text, return_tensors="pt").to(device)
            with torch.no_grad():
                gemma_outputs = gemma_model(**gemma_inputs, output_hidden_states=True)
                gemma_hidden = gemma_outputs.hidden_states[-1].to(torch.float32)
            
            # --- Router ---
            qwen_soft_prompts, _ = router(gemma_hidden)
            qwen_soft_prompts_bf16 = qwen_soft_prompts.to(qwen_model.dtype)

            # --- Qwen: Forward for Loss ---
            qwen_target_inputs = qwen_tokenizer(text, return_tensors="pt").to(device)
            target_ids = qwen_target_inputs.input_ids
            
            with torch.no_grad():
                target_embeds = qwen_model.get_input_embeddings()(target_ids)
                
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
            
            # Gradient Accumulation
            loss = loss / accumulation_steps
            loss.backward()
            epoch_loss += loss.item() * accumulation_steps
            
            # Update weights every accumulation_steps
            if (i + 1) % accumulation_steps == 0 or (i + 1) == len(train_texts):
                torch.nn.utils.clip_grad_norm_(router.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1
                
                # Update progress bar
                current_lr = scheduler.get_last_lr()[0]
                pbar.set_postfix({"Loss": f"{loss.item() * accumulation_steps:.4f}", "LR": f"{current_lr:.2e}"})
                
        avg_epoch_loss = epoch_loss / len(train_texts)
        print(f"[*] Epoch {epoch+1} Average Loss: {avg_epoch_loss:.4f}")
        
        # Save checkpoint
        ckpt_path = f"jcross_telepathy_router_general_epoch{epoch+1}.pt"
        torch.save(router.state_dict(), ckpt_path)
        print(f"[*] Saved checkpoint: {ckpt_path}")

    print("\\n[*] Training Complete. Saved final weights.")

if __name__ == "__main__":
    train()
