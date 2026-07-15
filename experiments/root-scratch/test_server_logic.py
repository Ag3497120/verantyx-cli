import json
import mlx.core as mx
from transformers import AutoTokenizer
from outlines.models.mlxlm import MLXLM
from outlines.generator import get_json_schema_logits_processor

# Dummy Model to test the wrapper
class DummyModel:
    pass

model = DummyModel()
tokenizer = AutoTokenizer.from_pretrained("/Users/motonishikoudai/Library/Caches/models/kofdai/talkie-1930-13b-it-mlx-8bit")

outlines_model = MLXLM(model, tokenizer)
schema_dict = {
    "type": "object",
    "properties": {
        "target_node_id": {"type": "string"},
        "new_structure": {"type": "string"}
    },
    "required": ["target_node_id", "new_structure"]
}

logits_processor = get_json_schema_logits_processor("outlines_core", outlines_model, json.dumps(schema_dict))

input_ids = mx.array([[1, 2, 3]])
logits = mx.zeros((1, 65536))

processed = logits_processor(input_ids, logits)
print(processed.shape)
print("SUCCESS")
