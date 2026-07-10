import argparse
import json
import torch
import sys
from transformers import AutoModelForCausalLM, AutoTokenizer
import time

def main():
    parser = argparse.ArgumentParser(description="Verantyx Pure Coder (Translator)")
    parser.add_argument("--input", required=True, help="Path to input JSON file with vector")
    parser.add_argument("--system-prompt", required=False, default="You are a pure syntax translator. Output valid code.")
    args = parser.parse_args()

    # 1. Load Intent Vector
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    vector_list = data["vector"]
    intent_vector = torch.tensor(vector_list, dtype=torch.float32).view(1, -1)

    model_id = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a"
    print("[Coder] Loading Qwen-9B for synthesis...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    # Use CPU to avoid MPS shape inference bugs during generation, or MPS if stable.
    # We will use CPU to ensure it works for now.
    model = AutoModelForCausalLM.from_pretrained(
        model_id, 
        device_map="cpu", 
        torch_dtype=torch.float32,
        trust_remote_code=True
    )

    intent_vector = intent_vector.to(model.device)

    # 2. Extract Vocabulary Embeddings (LM Head / Input Embeds)
    embedding_layer = model.get_input_embeddings()
    vocab_embeddings = embedding_layer.weight # Shape: (vocab_size, hidden_dim)

    # 3. Resynthesize vector into strict token manifold to prevent OOD (Chinese Swamp)
    print("[Coder] Mathematically locking intent into token manifold (OOD Prevention)...", file=sys.stderr)
    
    # Qwen-9B vocabulary embedding is shape (vocab_size, 3584).
    # intent_vector is shape (1, 3584). 
    # To get logits (1, vocab_size), we multiply intent_vector by vocab_embeddings.T
    logits = torch.matmul(intent_vector, vocab_embeddings.T)
    temperature = 0.1
    soft_probs = torch.nn.functional.softmax(logits / temperature, dim=-1)
    thought_embeds = torch.matmul(soft_probs, vocab_embeddings) # Shape: (1, hidden_dim)
    thought_embeds = thought_embeds.unsqueeze(1) # Shape: (1, 1, hidden_dim)

    # 4. Create Syntax Anchor
    messages = [
        {"role": "system", "content": args.system_prompt},
        {"role": "user", "content": "Decode the telepathic intent vector."}
    ]
    prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    syntax_ids = tokenizer.encode(prompt_text, return_tensors="pt").to(model.device)
    syntax_embeds = embedding_layer(syntax_ids)

    # 5. Concatenate: [Syntax Anchor] + [Pure Thought Vector]
    inputs_embeds = torch.cat([syntax_embeds, thought_embeds], dim=1)

    print("[Coder] Starting autoregressive generation...", file=sys.stderr)
    
    generated_ids = []
    past_key_values = None
    current_embeds = inputs_embeds
    
    max_new_tokens = 100
    for i in range(max_new_tokens):
        with torch.no_grad():
            outputs = model(
                inputs_embeds=current_embeds,
                past_key_values=past_key_values,
                use_cache=True
            )
            
        past_key_values = outputs.past_key_values
        next_token_logits = outputs.logits[:, -1, :]
        next_token = torch.argmax(next_token_logits, dim=-1)
        generated_ids.append(next_token.item())
        
        token_str = tokenizer.decode([next_token.item()])
        print(token_str, end="", file=sys.stderr, flush=True)
        
        if next_token.item() in [tokenizer.eos_token_id, 151645]: # 151645 is chatml eos
            break
            
        current_embeds = embedding_layer(next_token).unsqueeze(0)
        
    print("\n", file=sys.stderr)
    final_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    print(final_text) # Output to stdout for TS orchestrator to capture

if __name__ == "__main__":
    main()
