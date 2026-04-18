import requests
import json
payload = {
    "model": "gemma4:26b",
    "prompt": "Say hello world.",
    "stream": False,
    "options": {"temperature": 0.0}
}
res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=90)
print(res.text)
