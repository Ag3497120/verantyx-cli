import mlx.core as mx
import requests
import json

response = requests.post("http://127.0.0.1:8000/v1/chat/completions", json={
    "messages": [{"role": "user", "content": "1930年代の新聞記事について書いてください。"}],
    "max_tokens": 1,
    "stream": False
})
print(response.text)
