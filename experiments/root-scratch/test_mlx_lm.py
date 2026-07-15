from mlx_lm import load, generate
model_path = "/Users/motonishikoudai/verantyx-cli/model_4bit"
model, tokenizer = load(model_path)
print("Model loaded successfully with mlx_lm!")
prompt = "[INST] 1930年代の新聞記事を書いてください。 [/INST]"
text = generate(model, tokenizer, prompt=prompt, max_tokens=20, verbose=True)
print("Text generated successfully!")
