from transformers import AutoConfig
config = AutoConfig.from_pretrained("Qwen/Qwen3.6-27B", trust_remote_code=True)
print(config.intermediate_size)
