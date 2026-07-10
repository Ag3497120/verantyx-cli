import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.6-27B", trust_remote_code=True, device_map="auto", torch_dtype=torch.float16)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.6-27B", trust_remote_code=True)

prompt = "<|im_start|>user\nWhat is the capital of France?<|im_end|>\n<|im_start|>assistant\n"
input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to(model.device)

with torch.no_grad():
    outputs = model(input_ids, output_hidden_states=True)
    
print("First token embedding:", outputs.hidden_states[0][0, 0, :5].tolist())
print("Last token hidden state:", outputs.hidden_states[-1][0, -1, :5].tolist())

logits = outputs.logits[0, -1, :]
topk = torch.topk(logits, 5)
print("Top 5 logits:", topk.values.tolist(), topk.indices.tolist())

# Generate next token
gen = model.generate(input_ids, max_new_tokens=1)
print("Generated token:", gen[0, -1].item())
