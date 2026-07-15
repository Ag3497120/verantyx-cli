with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()
import re
text = re.sub(r'self\.hf_model = AutoModelForCausalLM\.from_pretrained\("Qwen/Qwen3\.5-9B", torch_dtype=torch\.float16\)\.to\(device\)', r'self.hf_model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-9B", torch_dtype=torch.float32).to("cpu")', text)
with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)
