import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:26b"

SYSTEM_PROMPT = """[System Directive]
あなたは Verantyx Cortex の推論エンジンです。
ユーザーに返答する前に、必ず以下の <jcross_thought> タグ内で、あなたの思考と現在のコンテキストを「JCross 空間トポロジー形式」で記述しなさい。
このブロックはあなたの内部記憶（L1キャッシュ）として永続化されます。
その後、<response> タグ内で、ユーザーに向けた自然言語（日本語/英語）の回答を出力しなさい。

[Output Format]
<jcross_thought>
■ JCROSS_NODE_current
【空間座相】 [探:0.8] [認:0.9]
【次元概念】 (10単語以内でトピックを厳格に記述)
【連帯】 (関連する過去のノードIDがあれば記述)
[本質記憶] (対話の要言を圧縮して記述)
</jcross_thought>

<response>
（ここにユーザーへの親しみやすい自然言語の回答）
</response>
"""

QUESTION = "黄河文明とメソポタミア文明の最大の違いについて教えてください。"

payload = {
    "model": MODEL,
    "prompt": f"{SYSTEM_PROMPT}\n\nUser: {QUESTION}\n",
    "stream": False,
    "options": {
        "temperature": 0.3
    }
}

print(f"Testing Invisible Monologue on {MODEL}...")
try:
    res = requests.post(OLLAMA_URL, json=payload, timeout=60)
    print("\n--- Output ---")
    print(res.json().get('response', 'No response'))
except Exception as e:
    print(f"Error: {e}")
