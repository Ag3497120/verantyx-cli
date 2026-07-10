import json
from transformers import AutoTokenizer
from outlines.fsm.json_schema import build_regex_from_schema
from outlines.fsm.fsm import RegexFSM
from outlines.models.transformers import TransformerTokenizer

tokenizer = AutoTokenizer.from_pretrained("/Users/motonishikoudai/Library/Caches/models/kofdai/talkie-1930-13b-it-mlx-8bit")
outlines_tokenizer = TransformerTokenizer(tokenizer)

schema = {
    "type": "object",
    "properties": {
        "target_node_id": {"type": "string"},
        "operation": {"type": "string"},
        "new_structure": {"type": "string"}
    },
    "required": ["target_node_id", "operation", "new_structure"]
}
regex_str = build_regex_from_schema(json.dumps(schema))
fsm = RegexFSM(regex_str, outlines_tokenizer)

state = fsm.default_state
print("Initial state:", state)
allowed = fsm.allowed_token_ids(state)
print("Allowed tokens:", len(allowed), allowed[:10] if type(allowed) == list else allowed)

# To check mask logic
import mlx.core as mx
logits = mx.zeros((1, 65536))
mask = mx.full(logits.shape, float("-inf"))
# If allowed tokens is an iterable of ints
for token_id in allowed:
    mask[0, token_id] = 0.0

print(mask)
