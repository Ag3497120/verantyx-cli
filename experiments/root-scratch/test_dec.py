from transformers import AutoTokenizer
model_path = "/Users/motonishikoudai/Library/Caches/models/kofdai/talkie-1930-13b-it-mlx-8bit"
tokenizer = AutoTokenizer.from_pretrained(model_path)
for t in [44, 283, 258, 497, 270]:
    print(repr(tokenizer.decode([t])))
