import requests
from typing import List, Optional

# Re-use the existing LLM configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e2b"

NUANCE_PROMPT = """You are a highly precise linguistic/nuance dictionary operating within a JCross Symbolic Engine.
The Symbolic Engine cannot find an exact word overlap for the user's query.

User Query: "{query}"

Available Symbolic Nodes connected in the Graph:
{available_nodes}

Task: Which specific node from the list above BEST matches the nuance or intent of the user's query? 
Rules:
- Respond ONLY with the exact text of the matching node.
- Do NOT provide explanation.
- If none of them are even remotely close, respond with "NONE".
"""

class NuanceRouter:
    """
    LLM Context-Window as a Tool. Evaluates graph nodes that the deterministic
    engine thinks are totally disconnected, linking them via semantic nuance.
    """
    @staticmethod
    def resolve_nuance(query: str, adjacent_nodes: List[str]) -> Optional[str]:
        if not adjacent_nodes:
            return None
            
        nodes_str = "\n".join([f"- {n}" for n in adjacent_nodes])
        prompt = NUANCE_PROMPT.format(query=query, available_nodes=nodes_str)
        
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0} # Pure deterministic dictionary lookup
        }
        
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=20)
            if res.status_code == 200:
                answer = res.json().get("response", "").strip()
                if answer == "NONE":
                    return None
                return answer
            else:
                print(f"[NuanceRouter] API Error: {res.status_code}")
        except Exception as e:
            print(f"[NuanceRouter] LLM Timeout / Error: {e}")
            return None
        return None
