import json

# Generate a dummy intent vector of size 4096 (Qwen-9B hidden dim)
dummy_vector = [0.1] * 4096
with open("temp_intent.json", "w") as f:
    json.dump({"vector": dummy_vector}, f)

print("Created temp_intent.json (4096 dim)")
