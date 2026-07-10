from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.6-27B", trust_remote_code=True)
print(tokenizer.encode("<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\n"))
