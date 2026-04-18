import json
import requests
import traceback
import subprocess
import os

TARGET_DIR = "/Users/motonishikoudai/verantyx-cli/verantyx-browser/.ronin/jcross_v7"
QUERY_BIN = "/Users/motonishikoudai/verantyx-cli/verantyx-browser/target/release/examples/query_jcross"
MODEL = "gemma4:26b"
OLLAMA_URL = "http://localhost:11434/api/generate"

def query_jcross(q_text, limit=5):
    query_input = {"queries": [q_text], "limit": limit}
    res = subprocess.run([QUERY_BIN, json.dumps(query_input)], capture_output=True, text=True, env={**os.environ, "JCROSS_TARGET_DIR": TARGET_DIR})
    if res.returncode == 0:
        out_lines = res.stdout.strip().split('\n')
        for line in reversed(out_lines):
            if line.strip().startswith('{'):
                try:
                    return json.loads(line).get("results", [])
                except json.JSONDecodeError:
                    continue
    return []

q = "I'm checking our previous chat about the shift rotation sheet for GM social media agents. Can you remind me what was the rotation for Admon on a Sunday?"
evidence_nodes = query_jcross(q, limit=5)
print("Evidence found:", len(evidence_nodes))

evidence_text = "\n\n".join([f"--- Chunk [{n['key']}] ---\n{n['content']}" for n in evidence_nodes])
print("Evidence text length:", len(evidence_text))

SYSTEM_PROMPT = """You are an AI assistant answering questions based on your raw memory L2 archive.
Use the following evidence to answer. Be concise and keep your answers brief.

[Question]
{question}

[L2 Archive Raw Evidence Nodes]
{evidence}
"""

prompt = SYSTEM_PROMPT.format(question=q, evidence=evidence_text)
payload = {
    "model": MODEL,
    "prompt": prompt,
    "stream": False,
    "options": {"temperature": 0.2}
}

try:
    print("Calling Ollama...")
    res = requests.post(OLLAMA_URL, json=payload, timeout=90)
    print("Ollama status code:", res.status_code)
    try:
        data = res.json()
        print("Keys:", data.keys())
        if 'error' in data:
            print("ERROR from Ollama:", data['error'])
    except:
        print("Raw unparseable text:", res.text[:200])
except Exception as e:
    traceback.print_exc()
