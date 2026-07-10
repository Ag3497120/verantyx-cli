import urllib.request
import json
url = "https://huggingface.co/Qwen/Qwen2.5-3B/raw/main/modeling_qwen2_5.py"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    with open("modeling_qwen2_5.py", "wb") as f:
        f.write(html)
    print("Downloaded modeling_qwen2_5.py")
except Exception as e:
    print(f"Failed: {e}")
