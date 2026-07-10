from transformers import AutoTokenizer
import sys

tokenizer = AutoTokenizer.from_pretrained("THUDM/glm-4-9b-chat", trust_remote_code=True)
tokens = [86445, 2090, 16, 58594, 20241, 92464, 149569, 6128, 74002, 49716, 141747, 77848, 44519, 21, 92520, 8520, 20804, 22909, 6363, 22858]
print(tokenizer.decode(tokens))
