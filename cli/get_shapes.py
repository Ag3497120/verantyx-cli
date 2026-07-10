from transformers import AutoModelForCausalLM, AutoTokenizer
import urllib.request
import json
url = 'https://huggingface.co/Qwen/Qwen3.6-27B/raw/main/config.json'
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode('utf-8'))
except Exception as e:
    print('Failed to get config:', e)
