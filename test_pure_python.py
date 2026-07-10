import sys
import os
import torch
from cli.scripts.telepathic_coder import TelepathicCoder

def main():
    print("Initializing Telepathic Coder (Lossless, Full Local Inference)...")
    coder = TelepathicCoder(workspace_dir="/Users/motonishikoudai/verantyx-cli", cluster_mode=None)
    
    # Bypass the chat template and soft prompts
    # We will directly encode a raw string
    prompt = "# Advanced Python Calculator Application\n# Implements add, subtract, multiply, divide\nclass Calculator:\n"
    print(f"\n--- Testing Pure Python Autoregression ---")
    print(f"Prompt:\n{prompt}")
    
    input_ids = coder.tokenizer(prompt, return_tensors="pt").input_ids[0].to(coder.brain.device)
    
    # We will decode 100 tokens
    generated = input_ids.tolist()
    past_states = None
    
    with torch.no_grad():
        for step in range(100):
            if step == 0:
                x = coder.brain.embed_weight[input_ids].unsqueeze(0).to(torch.float16)
            else:
                last_token = generated[-1]
                x = coder.brain.embed_weight[last_token].unsqueeze(0).unsqueeze(0).to(torch.float16)
                
            x, past_states = coder.brain.forward_latent(x, past_states=past_states, role_name="Coder", mute_leakage=True)
            
            last_hidden = x[:, -1, :]
            if getattr(coder.brain, 'final_norm_weight', None) is not None:
                variance = last_hidden.pow(2).mean(-1, keepdim=True)
                last_hidden = (last_hidden * torch.rsqrt(variance + 1e-6)).to(torch.float16)
                last_hidden = (last_hidden * coder.brain.final_norm_weight).to(torch.float16)
                
            logits = torch.matmul(last_hidden, coder.brain.lm_head_weight.to(torch.float16).T)
            
            # Simple Greedy Decoding
            next_token = torch.argmax(logits[0]).item()
            generated.append(next_token)
            
            print(coder.tokenizer.decode([next_token]), end="", flush=True)
            
            if next_token == coder.tokenizer.eos_token_id:
                break
                
    print("\n\n--- Finished ---")

if __name__ == "__main__":
    main()
