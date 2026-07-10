import torch

head_dim = 256
rotary_dim = int(head_dim * 0.25)
base = 10000000.0

# Method 1: Using rotary_dim in exponent (like standard RoPE applied to subset)
inv_freq1 = 1.0 / (base ** (torch.arange(0, rotary_dim, 2).float() / rotary_dim))

# Method 2: Using head_dim in exponent (HuggingFace usually uses the rotary_dim, but let's check what Qwen actually does)
inv_freq2 = 1.0 / (base ** (torch.arange(0, rotary_dim, 2).float() / head_dim))

print("Method 1:", inv_freq1[:5])
print("Method 2:", inv_freq2[:5])
