import os
import os
import re

def clean_wiki_text(text: str) -> list:
    """Split wiki text into manageable sentence chunks."""
    text = re.sub(r'\[\d+\]', '', text) # remove citations
    sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20]
    return sentences

import requests

def ingest_wikipedia_to_jcross(topic: str, target_dir: str):
    print(f"Fetching Wikipedia article for topic: {topic}")
    
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '_')}"
    headers = {'User-Agent': 'VerantyxBot/1.0 (mz@verantyx.ai)'}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Topic '{topic}' does not exist on Wikipedia or could not be loaded.")
        return
        
    data = response.json()
    os.makedirs(target_dir, exist_ok=True)
    out_file = os.path.join(target_dir, f"wiki_facts_{topic.replace(' ', '_').lower()}.jcross")
    
    print(f"Article found: {data.get('title')}")
    sentences = clean_wiki_text(data.get('extract', ''))
    
    # In a full production run, we would pass 'sentences' through PuzzleInference Engine.
    # Here, we will map the sentences as raw foundational blocks into the JCross Graph,
    # treating the topic as the core Gravity Node.
    
    title = data.get('title', 'Unknown')
    with open(out_file, "w", encoding="utf-8") as f:
        # Base Node
        node_id = f"WIKI_{title.replace(' ', '_')}"
        f.write(f"■ JCROSS_{node_id}\n")
        f.write("【空間座相】\n")
        f.write("[重:50.0] [核:10.0]\n") # Massive gravity because it's a root concept
        
        f.write("【連帯】\n")
        # Categories placeholder since we are using plain REST API now
        f.write(f"WIKI_CAT_Concept:属:1.0\n")
            
        # The sentences act as semantic memory payloads
        f.write("【本質記憶】\n")
        for s in sentences:
            f.write(f"- {s}.\n")
        
        # Link out to the most prominent links in the summary
        f.write("\n")
        
    print(f"✅ Ingestion Complete! Saved out {len(sentences)} conceptual facts to {out_file}.")

if __name__ == "__main__":
    target = os.path.join(os.path.dirname(__file__), "ontologies")
    ingest_wikipedia_to_jcross("Artificial intelligence", target)
    ingest_wikipedia_to_jcross("Information retrieval", target)
