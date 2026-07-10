import urllib.request
url = "https://huggingface.co/THUDM/glm-4-9b/raw/main/modeling_chatglm.py"
urllib.request.urlretrieve(url, "modeling_chatglm.py")
