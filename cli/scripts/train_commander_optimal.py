import os
import sys
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForCausalLM
from torch.optim import AdamW
import gc
import json

MODEL_ID = "google/gemma-4-12B"
DATASET_FILE = "cli/scripts/healing_dataset.jsonl"
TRANSLATOR_PATH = "models/jcross_translator_latest.pt"

# Ensure we have the Translator class
from train_translator import JCrossTranslator

def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Optimal Commander Healing on {device}...")
    
    # 1. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, local_files_only=True)
    
    # 2. Load the optimal healing dataset
    if not os.path.exists(DATASET_FILE):
        print(f"[-] Error: Could not find {DATASET_FILE}.")
        return
        
    dataset_texts = []
    with open(DATASET_FILE, "r") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    if "text" in data:
                        # Clean up <bos> if tokenizer already adds it
                        t = data["text"].replace("<bos>", "")
                        dataset_texts.append(t)
                except:
                    pass
        
    print(f"[*] Loaded {len(dataset_texts)} Optimal Stimulus Examples.")
    
    # 3. Load Frozen Base Model
    print(f"[*] Loading frozen base model: {MODEL_ID}")
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float16, local_files_only=True)
    model.eval()
    for param in model.parameters():
        param.requires_grad = False
    model.to(device)
    
    # 4. Load or Initialize JCrossTranslator
    print(f"[*] Initializing JCrossTranslator (Soft Prompt Injector)...")
    translator = JCrossTranslator(jcross_dim=3840, gemma_dim=3840, num_soft_tokens=16)
    if os.path.exists(TRANSLATOR_PATH):
        try:
            translator.load_state_dict(torch.load(TRANSLATOR_PATH, map_location="cpu"))
            print("[*] Loaded existing translator weights.")
        except Exception as e:
            print(f"[-] Could not load existing translator: {e}. Starting fresh.")
    
    translator.to(device)
    translator.train()
    
    # 5. Training Setup
    optimizer = AdamW(translator.parameters(), lr=1e-4) # Slightly higher LR for fresh modulators
    EPOCHS = 4 # 4 Epochs for Optimal Healing
    
    print(f"[*] Commencing Soft-Prompt Optimal Healing (Next-Token Prediction)...")
    
    for epoch in range(EPOCHS):
        total_loss = 0
        for i, text in enumerate(dataset_texts):
            optimizer.zero_grad()
            
            # Encode text
            tokens = tokenizer(text, return_tensors="pt")
            input_ids = tokens.input_ids.to(device)
            
            # Extract text embeddings
            with torch.no_grad():
                text_embeds = model.get_input_embeddings()(input_ids)
            
            # Create a consistent dummy telepathy vector for this intent
            # Each text gets its own unique vector so the Translator doesn't learn contradictory mappings
            intent_id = i + 1
            concept_vector = torch.ones((1, 3840), dtype=torch.float32, device=device) * intent_id
            
            # Translate vector to soft prompts
            soft_prompts = translator(concept_vector) # [1, 16, 3840]
            
            # Combine (Convert soft prompts to float16 to match text_embeds)
            inputs_embeds = torch.cat([soft_prompts.to(torch.float16), text_embeds], dim=1)
            
            # Labels (ignore soft prompts)
            ignore_labels = torch.full((1, 16), -100, dtype=torch.long, device=device)
            labels = torch.cat([ignore_labels, input_ids], dim=1)
            
            # Forward pass
            outputs = model(inputs_embeds=inputs_embeds, labels=labels)
            loss = outputs.loss
            
            # Backward
            loss.backward()
            
            # Gradient clipping to prevent NaN
            torch.nn.utils.clip_grad_norm_(translator.parameters(), max_norm=1.0)
            
            optimizer.step()
            total_loss += loss.item()
            
        avg_loss = total_loss / len(dataset_texts)
        print(f"  Epoch {epoch+1:03d}/{EPOCHS} | Avg Loss: {avg_loss:.4f}")
            
    print(f"[*] Commander's Translator successfully healed!")
    
    # Save the updated translator
    os.makedirs(os.path.dirname(TRANSLATOR_PATH), exist_ok=True)
    torch.save(translator.state_dict(), TRANSLATOR_PATH)
    print(f"[*] Saved optimal translator to {TRANSLATOR_PATH}")
    
    del model
    del translator
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    elif torch.cuda.is_available():
        torch.cuda.empty_cache()

if __name__ == "__main__":
    main()
