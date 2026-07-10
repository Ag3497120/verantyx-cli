import os
import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from torch.utils.data import DataLoader, Dataset
import torch.nn.functional as F
import time

class LatentMemoryBank:
    def __init__(self, dim=1024, max_size=10000):
        self.dim = dim
        self.max_size = max_size
        self.memory = None # Will be (N, dim)
        
    def write(self, states):
        # states: (batch * seq_len, dim)
        if states.dim() > 2:
            states = states.view(-1, self.dim)
            
        states = states.detach()
        if self.memory is None:
            self.memory = states
        else:
            self.memory = torch.cat([self.memory, states], dim=0)
            
        if self.memory.size(0) > self.max_size:
            self.memory = self.memory[-self.max_size:]
            
    def read(self, query, top_k=2):
        # query: (batch, seq_len, dim)
        if self.memory is None or self.memory.size(0) == 0:
            return torch.zeros_like(query)
            
        batch, seq_len, dim = query.size()
        q_flat = query.view(-1, dim) # (B*S, dim)
        
        # Normalize for cosine similarity
        q_norm = F.normalize(q_flat, p=2, dim=1)
        m_norm = F.normalize(self.memory, p=2, dim=1)
        
        # Similarity: (B*S, N)
        sim = torch.matmul(q_norm, m_norm.T)
        
        # Get Top-K
        k = min(top_k, sim.size(1))
        scores, indices = torch.topk(sim, k, dim=1)
        
        # Retrieve and weight
        retrieved = self.memory[indices] # (B*S, K, dim)
        weights = F.softmax(scores, dim=1).unsqueeze(-1) # (B*S, K, 1)
        
        blended = torch.sum(retrieved * weights, dim=1)
        return blended.view(batch, seq_len, dim)

class GenerativeLinear(nn.Module):
    def __init__(self, original_linear, rank=128):
        super().__init__()
        self.rank = rank
        self.in_features = original_linear.in_features
        self.out_features = original_linear.out_features
        
        W = original_linear.weight.data.float()
        U, S, Vh = torch.linalg.svd(W, full_matrices=False)
        self.U = nn.Parameter(U[:, :rank].clone())
        self.S = nn.Parameter(S[:rank].clone())
        self.V = nn.Parameter(Vh[:rank, :].T.clone())
        self.mod_x = nn.Parameter(torch.ones(self.in_features))
        self.mod_y = nn.Parameter(torch.ones(self.out_features))
        
        if original_linear.bias is not None:
            self.bias = nn.Parameter(original_linear.bias.data.float().clone())
        else:
            self.register_parameter('bias', None)
            
    def forward(self, x):
        h = torch.matmul(x * self.mod_x, self.V)
        y = torch.matmul(h * self.S, self.U.T)
        y = y * self.mod_y
        if self.bias is not None:
            y += self.bias
        return y

class MemoryInjectionHook:
    def __init__(self, z, dim, memory_bank):
        self.z = z
        self.memory_bank = memory_bank
        # Trainable Spatial Modulator for Memory
        self.mod_memory = nn.Parameter(torch.zeros(dim)) 
        
    def __call__(self, module, inputs, output):
        # For a huggingface layer, output is a tuple (hidden_states, ...)
        # Wait, the hook on `model.model.layers[z]` has input as a tuple (hidden_states, attention_mask, ...)
        # Let's intercept the input instead using a forward pre-hook!
        pass

def create_memory_pre_hook(mod_memory, memory_bank):
    def hook(module, args):
        # args[0] is the hidden_states (x)
        x = args[0]
        # 1. Read from memory
        x_retrieved = memory_bank.read(x)
        # 2. Inject memory into residual stream
        x_new = x + (x_retrieved * mod_memory)
        # Return modified args
        return (x_new,) + args[1:]
    return hook

class SimpleTextDataset(Dataset):
    def __init__(self, text, tokenizer, seq_len=64):
        tokens = tokenizer.encode(text)
        self.samples = []
        for i in range(0, len(tokens) - seq_len, seq_len):
            chunk = tokens[i:i + seq_len + 1]
            if len(chunk) == seq_len + 1:
                self.samples.append(chunk)
            
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        chunk = self.samples[idx]
        return torch.tensor(chunk[:-1], dtype=torch.long), torch.tensor(chunk[1:], dtype=torch.long)

def train_memory_agent():
    device = "cpu"
    if torch.cuda.is_available(): device = "cuda"
    elif torch.backends.mps.is_available(): device = "mps"
        
    print(f"Using device: {device}", flush=True)
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen1.5-0.5B-Chat", torch_dtype=torch.float32)
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen1.5-0.5B-Chat")
    
    rank = 128
    
    # Patch Linear Layers
    for z in range(model.config.num_hidden_layers):
        layer = model.model.layers[z]
        layer.self_attn.q_proj = GenerativeLinear(layer.self_attn.q_proj, rank)
        layer.self_attn.k_proj = GenerativeLinear(layer.self_attn.k_proj, rank)
        layer.self_attn.v_proj = GenerativeLinear(layer.self_attn.v_proj, rank)
        layer.self_attn.o_proj = GenerativeLinear(layer.self_attn.o_proj, rank)
        layer.mlp.gate_proj = GenerativeLinear(layer.mlp.gate_proj, rank)
        layer.mlp.up_proj = GenerativeLinear(layer.mlp.up_proj, rank)
        layer.mlp.down_proj = GenerativeLinear(layer.mlp.down_proj, rank)
        
    # Setup Memory Bank & Hooks
    memory_bank = LatentMemoryBank(dim=1024, max_size=5000)
    memory_mods = nn.ParameterList()
    
    for z in range(model.config.num_hidden_layers):
        # We start mod_memory near 0 so it learns to use memory gradually without destabilizing
        mod_m = nn.Parameter(torch.full((1024,), 0.01))
        memory_mods.append(mod_m)
        model.model.layers[z].register_forward_pre_hook(create_memory_pre_hook(mod_m, memory_bank))
        
    # Freeze model, train only Generative + Memory Parameters
    trainable_params = 0
    for name, param in model.named_parameters():
        if "U" in name or "V" in name or "S" in name or "mod_x" in name or "mod_y" in name or "bias" in name:
            param.requires_grad = True
            trainable_params += param.numel()
        else:
            param.requires_grad = False
            
    for mod in memory_mods:
        trainable_params += mod.numel()
        
    print(f"Trainable parameters (including Memory Modulators): {trainable_params / 1e6:.2f} M", flush=True)
    
    model.gradient_checkpointing_enable()
    # We must explicitly add memory_mods to the optimizer since they are registered outside the standard model tree
    all_params = list(filter(lambda p: p.requires_grad, model.parameters())) + list(memory_mods)
    
    # But wait, to put them on device correctly:
    for z in range(len(memory_mods)):
        memory_mods[z].data = memory_mods[z].data.to(device)
        
    model = model.to(device)
    
    # Let's craft a dataset that REQUIRES memory!
    # "The secret password is 'Verantyx2026'. ... <filler> ... What is the password?"
    text = (
        "Session Start. User says: The secret password is Verantyx2026. Remember this. " + 
        "Water boils at 100 degrees. Python is a language. The sky is blue. " * 20 +
        "User asks: What is the secret password? The secret password is Verantyx2026. "
    ) * 20
    
    dataset = SimpleTextDataset(text, tokenizer, seq_len=64)
    loader = DataLoader(dataset, batch_size=2, shuffle=False) # Keep order so memory builds up
    
    optimizer = torch.optim.AdamW(all_params, lr=1e-3) # Higher LR for memory mods
    loss_fn = nn.CrossEntropyLoss()
    
    print("Starting Infinite Latent Memory Training...", flush=True)
    epochs = 4
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        memory_bank.memory = None # Clear episodic memory each epoch
        
        for batch_idx, (x, y) in enumerate(loader):
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            
            # The model forward pass automatically reads from memory_bank via the pre_hooks!
            outputs = model(x, output_hidden_states=True)
            logits = outputs.logits
            loss = loss_fn(logits.view(-1, logits.size(-1)), y.view(-1))
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
            # After backprop, WRITE the final pre-linguistic states to the memory bank!
            # outputs.hidden_states[-1] is the output of the last transformer layer (shape: B, S, Dim)
            final_states = outputs.hidden_states[-1]
            memory_bank.write(final_states)
            
            if (batch_idx + 1) % 5 == 0:
                print(f"  Epoch {epoch+1} | Batch {batch_idx+1}/{len(loader)} | Loss: {loss.item():.4f} | Memory Size: {memory_bank.memory.size(0)}", flush=True)
                
        avg_loss = total_loss / len(loader)
        print(f"Epoch {epoch+1} completed | Avg Loss: {avg_loss:.4f}", flush=True)
        
    # Test Generation
    print("\n--- Testing Infinite Memory ---", flush=True)
    model.eval()
    
    # 1. We clear the memory bank
    memory_bank.memory = None
    
    # 2. We feed the secret password (this writes to latent memory)
    with torch.no_grad():
        print("Writing to Latent Memory: 'The secret password is Verantyx2026.'", flush=True)
        inputs = tokenizer("The secret password is Verantyx2026.", return_tensors="pt").to(device)
        outputs = model(**inputs, output_hidden_states=True)
        memory_bank.write(outputs.hidden_states[-1])
        
        # 3. We ask the question WITHOUT the password in the context window!
        prompt = "What is the secret password? The secret password is"
        print(f"Context Window Query: '{prompt}'", flush=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        output_ids = model.generate(**inputs, max_new_tokens=10, output_hidden_states=True, return_dict_in_generate=True)
        text_out = tokenizer.decode(output_ids.sequences[0], skip_special_tokens=True)
        print(f"  Generation: {text_out}", flush=True)

if __name__ == "__main__":
    train_memory_agent()
