from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained('THUDM/glm-4-9b-chat', trust_remote_code=True)
prompt = "ユーザー: こんにちは、GLM-5.2！自己紹介をして。\nアシスタント: "
print(tokenizer.encode(prompt))
