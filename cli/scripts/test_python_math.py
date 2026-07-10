import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForCausalLM
import numpy as np

def rms_norm(x, weight, eps=1e-6):
    variance = x.pow(2).mean(-1, keepdim=True)
    x = x * torch.rsqrt(variance + eps)
    return x * weight

def apply_rope(q, k, pos, head_dim=64):
    freqs = torch.arange(0, head_dim, 2, dtype=torch.float32)
    inv_freq = 1.0 / (10000.0 ** (freqs / head_dim))
    
    freqs = pos * inv_freq
    freqs = torch.cat((freqs, freqs), dim=-1)
    
    sin = torch.sin(freqs)
    cos = torch.cos(freqs)
    
    def rotate(t):
        t1, t2 = t[..., :head_dim//2], t[..., head_dim//2:]
        return torch.cat((-t2, t1), dim=-1)
        
    q_out = q.view(-1, head_dim)
    q_out = (q_out * cos) + (rotate(q_out) * sin)
    
    k_out = k.view(-1, head_dim)
    k_out = (k_out * cos) + (rotate(k_out) * sin)
    
    return q_out.flatten(), k_out.flatten()

def generate(prompt, max_tokens=20):
    print("Loading original weights for math test...")
    hf_model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen1.5-0.5B-Chat")
    state_dict = hf_model.state_dict()
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen1.5-0.5B-Chat")
    
    input_ids = tokenizer.encode(prompt)
    print(f"Input: {prompt}")
    
    layers = 24
    head_dim = 64
    num_q_heads = 1024 // 64
    num_kv_heads = 1024 // 64
    
    kv_cache = {z: {'k': [], 'v': []} for z in range(layers)}
    
    for t in range(max_tokens):
        token = input_ids[-1]
        x = state_dict["model.embed_tokens.weight"][token].float()
        pos = len(input_ids) - 1
        
        for z in range(layers):
            residual = x
            
            x = rms_norm(x, state_dict[f"model.layers.{z}.input_layernorm.weight"].float())
            
            q = torch.matmul(state_dict[f"model.layers.{z}.self_attn.q_proj.weight"].float(), x)
            # Qwen adds bias to q, k, v!
            q += state_dict[f"model.layers.{z}.self_attn.q_proj.bias"].float()
            
            k = torch.matmul(state_dict[f"model.layers.{z}.self_attn.k_proj.weight"].float(), x)
            k += state_dict[f"model.layers.{z}.self_attn.k_proj.bias"].float()
            
            v = torch.matmul(state_dict[f"model.layers.{z}.self_attn.v_proj.weight"].float(), x)
            v += state_dict[f"model.layers.{z}.self_attn.v_proj.bias"].float()
            
            q, k = apply_rope(q, k, pos, head_dim)
            
            kv_cache[z]['k'].append(k)
            kv_cache[z]['v'].append(v)
            
            K = torch.stack(kv_cache[z]['k'])
            V = torch.stack(kv_cache[z]['v'])
            
            q = q.view(num_q_heads, head_dim)
            K = K.view(-1, num_kv_heads, head_dim)
            V = V.view(-1, num_kv_heads, head_dim)
            
            attn_out = torch.zeros_like(q)
            for h in range(num_q_heads):
                q_h = q[h]
                K_h = K[:, h, :]
                V_h = V[:, h, :]
                
                scores = torch.matmul(K_h, q_h) / (head_dim ** 0.5)
                probs = torch.softmax(scores, dim=0)
                attn_out[h] = torch.matmul(probs, V_h)
                
            attn_out = attn_out.flatten()
            
            x = torch.matmul(state_dict[f"model.layers.{z}.self_attn.o_proj.weight"].float(), attn_out)
            
            x = x + residual
            residual = x
            
            x = rms_norm(x, state_dict[f"model.layers.{z}.post_attention_layernorm.weight"].float())
            
            gate = torch.matmul(state_dict[f"model.layers.{z}.mlp.gate_proj.weight"].float(), x)
            up = torch.matmul(state_dict[f"model.layers.{z}.mlp.up_proj.weight"].float(), x)
            
            swiglu = torch.nn.functional.silu(gate) * up
            
            x = torch.matmul(state_dict[f"model.layers.{z}.mlp.down_proj.weight"].float(), swiglu)
            
            x = x + residual
            
        x = rms_norm(x, state_dict['model.norm.weight'].float())
        logits = torch.matmul(state_dict['lm_head.weight'].float(), x)
        
        next_token = torch.argmax(logits).item()
        input_ids.append(next_token)
        
        print(tokenizer.decode([next_token]), end='', flush=True)

if __name__ == '__main__':
    generate("What is the capital of France? The capital of France is")
    print()
