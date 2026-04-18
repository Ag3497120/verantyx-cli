import os
import json
import requests
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b-instruct"

PROMPT_JCROSS_COMPRESSOR = """[System Directive]
You are a JCross Spatial Compiler. Your sole purpose is to translate the user's natural language into JCross compressed memory syntax. DO NOT output conversational text, explanations, or Markdown blocks (e.g. ```jcross). Output ONLY the raw JCross code.

[Memory Layers Instruction]
You must structure the output into exactly 3 levels of resolution:
1. Low-Res (Topology Summary): A short 1-2 character Kanji tag summarizing the situation, and a definition of that tag.
2. Mid-Res (Operational Logic): Detailed semantic mapping of verbs and nouns.
3. High-Res (Ground Truth Text): A verbatim copy of the raw text inside 【原文】.

[Operation Command Dictionary]
- OP.MAP("Entity Name", "[概念: ID]")         : Define an Entity/Object.
- OP.MAP_REL("Verb/Action", "[関係: ID]")    : Define an Action/Relation.
- OP.UNIFY("[概念: A]", "[関係: R]", "[概念: B]")   : Create a directional semantic edge.
- OP.COMPOSE("New_Action", "[関係: X]", "[関係: Y]") : Synthesize a new relation command if needed.

[Spatial Topology Parameters]
Based on emotional weight and urgency, assign Spatial Gravity to map where this memory floats on the Z-axis (Depth):
- [視: 0.0 - 1.0] (Focus/Visibility)
- [認: 0.0 - 1.0] (Epistemic certainty/Recognition)
- [庫: 0.0 - 1.0] (Deep storage depth. 1.0 is far back deep storage, 0.0 is very close immediate focus)
- [標: Kanji1・Kanji2] (1-2 character Kanji Summary Tag)

[Output Format Specification]
You MUST output EXACTLY this format, nothing else:

■ JCROSS_NODE_MEMORY_{ID}
【空間座相】
[視: {{0.0-1.0}}] [認: {{0.0-1.0}}] [庫: {{0.0-1.0}}] [標: {{Kanji}}]

【位相対応表】
[{{Kanji}}] := "Brief 1-sentence Japanese summary describing the gist of the tag."

【操作対応表】
(Define all MAP operations here based on the text entities)

【連帯】
(Define all UNIFY operations linking the above mapped concepts)

【原文】
{input_text}
"""

class JCrossCompiler:
    """
    Translates raw human conversational turns into Spatial Mathematical Memories
    using restricted Operation Commands.
    """
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.node_id_counter = 1

    def compress_to_jcross(self, text: str) -> Optional[str]:
        prompt = PROMPT_JCROSS_COMPRESSOR.format(
            ID=f"COMP_{self.node_id_counter}",
            input_text=text
        )
        self.node_id_counter += 1
        
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=60)
            if res.status_code == 200:
                out = res.json().get('response', '').strip()
                # Clean up markdown if LLM accidentally outputs it
                if out.startswith("```jcross"):
                    out = out[9:]
                if out.startswith("```"):
                    out = out[3:]
                if out.endswith("```"):
                    out = out[:-3]
                return out.strip()
        except Exception as e:
            print("Compiler Error:", str(e))
        return None

if __name__ == "__main__":
    compiler = JCrossCompiler()
    sample_text = "I desperately need to fix the critical bug in the authentication module before deployed tomorrow."
    print("Incoming Text:", sample_text)
    print("\n[Compiling Tri-Layer JCross...]\n")
    jcross_code = compiler.compress_to_jcross(sample_text)
    print(jcross_code)
