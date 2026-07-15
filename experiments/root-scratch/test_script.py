from transformers import AutoTokenizer
t = AutoTokenizer.from_pretrained('google/gemma-4-12B')
print(t.decode([0, 1, 2, 3]))
