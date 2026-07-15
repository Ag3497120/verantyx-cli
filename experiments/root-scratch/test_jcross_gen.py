import torch
from transformers import AutoTokenizer
import sys

# Load JCrossBrain
sys.path.append('cli/scripts')
from bucket_relay_swarm_experimental import JCrossBrain
device = "mps"
brain = JCrossBrain("cli/qwen_0.5b_full.jgen", device)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")

text = "The capital of France is"
tokens = tokenizer(text, return_tensors="pt").input_ids[0].to(device)

print("Prompt:", text)
emb = torch.nn.functional.embedding(tokens, brain.embed_weight).unsqueeze(0).to(torch.float16)

out_latents, past_states = brain.forward_latent(emb, past_states=None, mute_leakage=True)

last_hidden = out_latents[:, -1:, :]
generated = []

for i in range(20):
    if getattr(brain, 'final_norm_weight', None) is not None:
        variance = last_hidden.pow(2).mean(-1, keepdim=True)
        normed = last_hidden * torch.rsqrt(variance + 1e-6) * brain.final_norm_weight
    else:
        normed = last_hidden
        
    logits = torch.matmul(normed, brain.lm_head_weight.T)
    next_token = torch.argmax(logits.squeeze(1), dim=-1).item()
    generated.append(next_token)
    
    print(tokenizer.decode([next_token]), end="")
    sys.stdout.flush()
    
    next_emb = brain.embed_weight[next_token].unsqueeze(0).unsqueeze(0).to(torch.float16)
    out_latents, past_states = brain.forward_latent(next_emb, past_states=past_states, mute_leakage=True)
    last_hidden = out_latents[:, -1:, :]
print()
