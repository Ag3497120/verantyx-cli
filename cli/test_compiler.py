import torch
from safetensors import safe_open
import struct

def get_matrix_type(key):
    if "input_layernorm.weight" in key: return 0
    if "post_attention_layernorm.weight" in key: return 1
    if "linear_attn.conv1d" in key: return 2
    if "linear_attn.A_log" in key: return 3
    if "linear_attn.dt_bias" in key: return 4
    return 255

sf = safe_open("/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9/model-00008-of-00015.safetensors", framework="pt", device="cpu")
for key in sf.keys():
    if "layers.0.linear_attn.A_log" in key or "layers.0.linear_attn.dt_bias" in key:
        mtype = get_matrix_type(key)
        tensor = sf.get_tensor(key)
        if tensor.dtype != torch.float16:
            tensor = tensor.half()
        shape = list(tensor.shape)
        if len(shape) == 1 or "conv1d" in key:
            tensor_bytes = tensor.numpy().tobytes()
            print(f"Key: {key}, MType: {mtype}, Shape: {shape}, BytesLen: {len(tensor_bytes)}")
