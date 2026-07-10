import torch
import torch.nn as nn
from transformers import AutoTokenizer
import struct
import numpy as np

def load_jgen(filepath):
    tensors = {}
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        version = struct.unpack('<I', f.read(4))[0]
        num_layers, rank = struct.unpack('<I I', f.read(8))
        
        tensors['meta'] = {'layers': num_layers, 'rank': rank}
        
        while True:
            type_byte = f.read(1)
            if not type_byte:
                break
            btype = type_byte[0]
            
            if btype == 0:
                rows, cols = struct.unpack('<I I', f.read(8))
                data = np.frombuffer(f.read(rows * cols * 2), dtype=np.float16)
                tensors['embed'] = torch.from_numpy(data.copy()).reshape(rows, cols).float()
            elif btype == 1:
                rows, cols = struct.unpack('<I I', f.read(8))
                data = np.frombuffer(f.read(rows * cols * 2), dtype=np.float16)
                tensors['lm_head'] = torch.from_numpy(data.copy()).reshape(rows, cols).float()
            elif btype == 2:
                rows, cols = struct.unpack('<I I', f.read(8))
                data = np.frombuffer(f.read(rows * cols * 2), dtype=np.float16)
                tensors['final_norm'] = torch.from_numpy(data.copy()).reshape(rows).float()
            elif btype == 3:
                z, rows, cols = struct.unpack('<B I I', f.read(9))
                data = np.frombuffer(f.read(rows * cols * 2), dtype=np.float16)
                tensors[f'attn_norm_{z}'] = torch.from_numpy(data.copy()).reshape(rows).float()
            elif btype == 4:
                z, rows, cols = struct.unpack('<B I I', f.read(9))
                data = np.frombuffer(f.read(rows * cols * 2), dtype=np.float16)
                tensors[f'mlp_norm_{z}'] = torch.from_numpy(data.copy()).reshape(rows).float()
            elif btype == 5:
                z, mtype, rows, cols, mrank = struct.unpack('<B B I I I', f.read(14))
                
                u_data = np.frombuffer(f.read(rows * mrank * 2), dtype=np.float16)
                s_data = np.frombuffer(f.read(mrank * 2), dtype=np.float16)
                v_data = np.frombuffer(f.read(cols * mrank * 2), dtype=np.float16)
                mod_x_data = np.frombuffer(f.read(cols * 2), dtype=np.float16)
                mod_y_data = np.frombuffer(f.read(rows * 2), dtype=np.float16)
                
                U = torch.from_numpy(u_data.copy()).reshape(rows, mrank).float()
                S = torch.from_numpy(s_data.copy()).reshape(mrank).float()
                V = torch.from_numpy(v_data.copy()).reshape(cols, mrank).float()
                mod_x = torch.from_numpy(mod_x_data.copy()).reshape(cols).float()
                mod_y = torch.from_numpy(mod_y_data.copy()).reshape(rows).float()
                
                tensors[f'gen_{z}_{mtype}'] = (U, S, V, mod_x, mod_y)
                
    return tensors

def rms_norm(x, weight, eps=1e-6):
    variance = x.pow(2).mean(-1, keepdim=True)
    x = x * torch.rsqrt(variance + eps)
    return x * weight

def gen_matmul(x, gen_params):
    U, S, V, mod_x, mod_y = gen_params
    # x: (cols)
    # W_{ij} = (U_i * S * V_j^T) * mod_y_i * mod_x_j
    # We want y = x @ W^T  so y_i = \sum_j W_ij x_j
    
    # 1. h = V^T @ (x * mod_x)
    h = torch.matmul(V.T, x * mod_x)
    
    # 2. y = mod_y * (U @ (S * h))
    y = mod_y * torch.matmul(U, S * h)
    
    return y

def apply_rope(q, k, pos, head_dim=64):
    freqs = torch.arange(0, head_dim, 2, dtype=torch.float32)
    inv_freq = 1.0 / (10000.0 ** (freqs / head_dim))
    
    freqs = pos * inv_freq
    freqs = torch.cat((freqs, freqs), dim=-1)
    
    sin = torch.sin(freqs)
    cos = torch.cos(freqs)
    
    def rotate(t):
        # Llama/Qwen style: [x0, x1, ..., x_d/2-1, x_d/2, ... x_d-1] -> [-x_d/2, ..., -x_d-1, x0, ..., x_d/2-1]
        t1, t2 = t[..., :head_dim//2], t[..., head_dim//2:]
        return torch.cat((-t2, t1), dim=-1)
        
    q_out = q.view(-1, head_dim)
    q_out = (q_out * cos) + (rotate(q_out) * sin)
    
    k_out = k.view(-1, head_dim)
    k_out = (k_out * cos) + (rotate(k_out) * sin)
    
    return q_out.flatten(), k_out.flatten()

def generate(prompt, filepath="qwen_0.5b.jgen", max_tokens=20):
    print("Loading tensors...")
    tensors = load_jgen(filepath)
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen1.5-0.5B-Chat")
    
    input_ids = tokenizer.encode(prompt)
    print(f"Input: {prompt}")
    
    layers = tensors['meta']['layers']
    head_dim = 64
    num_q_heads = 1024 // 64
    num_kv_heads = 1024 // 64 # Wait, qwen 0.5b has MQA? Let me check config.
    # Qwen1.5 0.5B: hidden_size=1024, num_attention_heads=16, num_key_value_heads=16
    
    kv_cache = {z: {'k': [], 'v': []} for z in range(layers)}
    
    for t in range(max_tokens):
        # We only process the last token if we have a cache
        # For simplicity in this script, we'll just re-process everything (inefficient but exact)
        # Actually, let's just do standard KV caching for generation
        
        token = input_ids[-1]
        x = tensors['embed'][token]
        pos = len(input_ids) - 1
        
        for z in range(layers):
            residual = x
            
            # Attn Norm
            x = rms_norm(x, tensors[f'attn_norm_{z}'])
            
            # Q, K, V
            q = gen_matmul(x, tensors[f'gen_{z}_7'])
            k = gen_matmul(x, tensors[f'gen_{z}_8'])
            v = gen_matmul(x, tensors[f'gen_{z}_9'])
            
            # RoPE
            q, k = apply_rope(q, k, pos, head_dim)
            
            # Store KV cache
            kv_cache[z]['k'].append(k)
            kv_cache[z]['v'].append(v)
            
            # Attention (single token)
            K = torch.stack(kv_cache[z]['k']) # (seq_len, num_heads * head_dim)
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
            
            # O proj
            x = gen_matmul(attn_out, tensors[f'gen_{z}_20'])
            
            x = x + residual
            residual = x
            
            # MLP Norm
            x = rms_norm(x, tensors[f'mlp_norm_{z}'])
            
            # Gate, Up
            gate = gen_matmul(x, tensors[f'gen_{z}_10'])
            up = gen_matmul(x, tensors[f'gen_{z}_11'])
            
            # SwiGLU
            swiglu = torch.nn.functional.silu(gate) * up
            
            # Down
            x = gen_matmul(swiglu, tensors[f'gen_{z}_12'])
            
            x = x + residual
            
        x = rms_norm(x, tensors['final_norm'])
        logits = torch.matmul(tensors['lm_head'], x)
        
        next_token = torch.argmax(logits).item()
        input_ids.append(next_token)
        
        print(tokenizer.decode([next_token]), end='', flush=True)

if __name__ == '__main__':
    prompt = "1969年にアポロ11号に乗って、人類で初めて月面に降り立った宇宙飛行士の名前をフルネームで答えてください。"
    print(f"Prompt: {prompt}")
    generate(prompt, filepath="qwen_0.5b_trained.jgen", max_tokens=30)
    print()
