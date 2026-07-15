from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('google/gemma-4-12B')
print(f"pad={tok.pad_token_id}, image={tok.convert_tokens_to_ids('<image|>')}")
