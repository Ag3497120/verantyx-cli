import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a"
print("Loading Qwen 9B Tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
print("Loading Qwen 9B Model (this might take a minute)...")
model = AutoModelForCausalLM.from_pretrained(
    model_id, 
    device_map="cpu", 
    torch_dtype=torch.float16,
    trust_remote_code=True
)

blueprint = """
function calculate_hypotenuse(a: number, b: number): number {
    // Please implement Pythagorean theorem
}
"""

prompt = f"""<|im_start|>system
You are a pure syntax translator. You have no domain knowledge of the problem.
Your ONLY task is to translate the following provided implementation blueprint into valid syntax.
Do not add any logic or thinking outside of what is explicitly detailed in the blueprint.
<|im_end|>
<|im_start|>user
[IMPLEMENTATION BLUEPRINT]
{blueprint}

[OUTPUT EXPECTATION]
Output the translated code/text directly. Do not include <think> tags.
<|im_end|>
<|im_start|>assistant
"""

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
print("Generating translation...")
outputs = model.generate(**inputs, max_new_tokens=100, do_sample=False)
response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

print("\n=== CODER (TRANSLATOR) OUTPUT ===")
print(response)
print("=================================")
