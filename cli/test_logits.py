import torch, os
from transformers import AutoModelForCausalLM, AutoTokenizer

model_path = os.path.expanduser('~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')
tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
print('Loading model...')
model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16, device_map='cpu', trust_remote_code=True)
inputs = tok('<|im_start|>user\nWhat is the capital of France?<|im_end|>\n<|im_start|>assistant\n', return_tensors='pt')
print('Running forward pass...')
with torch.no_grad():
    out = model(**inputs)
    logits = out.logits[0, -1]
    print(f'Top logit: {logits.max().item()}')
    print(f'Top token ID: {logits.argmax().item()}')
    print(f'Token decoded: {tok.decode(logits.argmax().item())}')
