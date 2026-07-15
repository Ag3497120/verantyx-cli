import mlx.core as mx
from model_mlx import TalkieModelMLX, GPTConfig
import glob
from mlx.utils import tree_unflatten
import mlx.nn as nn
from transformers import AutoTokenizer

config = GPTConfig(vocab_size=65540, n_layer=40, n_head=40, n_embd=5120)
config.n_kv_head = 40
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
mx.eval(model.parameters())

tokenizer = AutoTokenizer.from_pretrained(model_path)
prompt = "[INST] 1930年代の新聞記事について書いてください。 [/INST]"
prompt_ids = tokenizer.encode(prompt, return_tensors="np")
prompt_ids = mx.array(prompt_ids)

cache = None
y = prompt_ids
print("Generating...")
for i in range(15):
    logits, cache = model(y, cache=cache)
    token_id = mx.argmax(logits, axis=-1).item()
    print(repr(tokenizer.decode([token_id])), end="", flush=True)
    y = mx.array([[token_id]])
print()
