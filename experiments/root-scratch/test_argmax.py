import mlx.core as mx
from model_mlx import TalkieModelMLX, GPTConfig
import glob
from mlx.utils import tree_unflatten
import mlx.nn as nn

config_dict = {"vocab_size": 65540, "num_hidden_layers": 40, "num_attention_heads": 40, "hidden_size": 5120, "num_key_value_heads": 40}
config = GPTConfig(
    vocab_size=config_dict.get("vocab_size", 65540),
    n_layer=config_dict.get("num_hidden_layers", 40),
    n_head=config_dict.get("num_attention_heads", 40),
    n_embd=config_dict.get("hidden_size", 5120),
)
config.n_kv_head = config_dict["num_key_value_heads"]

model = TalkieModelMLX(config)
def quant_predicate(path, m):
    if not isinstance(m, nn.Linear):
        return False
    quant_names = ["attn_query", "attn_key", "attn_value", "mlp_gate", "mlp_linear"]
    for name in quant_names:
        if name in path:
            return True
    return False

nn.quantize(model, group_size=64, bits=8, class_predicate=quant_predicate)

model_path = "/Users/motonishikoudai/Library/Caches/models/kofdai/talkie-1930-13b-it-mlx-8bit"
weight_files = glob.glob(f"{model_path}/*.safetensors")
weights = {}
for w in weight_files:
    weights.update(mx.load(w))
weights = tree_unflatten(list(weights.items()))
model.update(weights)

prompt_ids = mx.array([[1, 29871, 31326]])
logits, _ = model(prompt_ids)
token_id = mx.argmax(logits, axis=-1).item()
print(f"Token ID: {token_id}")

from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(model_path)
print(f"Tokenizer vocab size: {len(tokenizer)}")
print(f"Decoded token: {tokenizer.decode([token_id])}")
