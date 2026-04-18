import os
import nltk

try:
    nltk.download('wordnet', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except Exception:
    pass

from nltk.corpus import wordnet as wn
from collections import Counter

def run_lexicon_forge():
    print("🔥 Starting Pure CPU Lexicon Forge via NLTK WordNet...")
    
    # We want top 1000 most common distinct verbs with robust synonyms
    # We can gather frequency or just take the first 1000 non-obscure verbs.
    # To keep it relevant, let's collect all verb synsets and sort by frequency or length of lemmas.
    verb_synsets = list(wn.all_synsets('v'))
    
    # Sort by the number of lemmas (more synonyms implies more common/fundamental)
    verb_synsets.sort(key=lambda s: len(s.lemmas()), reverse=True)
    
    lexicon_file = "src/verantyx/knowledge_base/core_lexicon.jcross"
    total_generated = 0
    
    # Take the top 1000 most synonymous verbs
    top_synsets = verb_synsets[:1000]
    
    out_blocks = []
    
    for s in top_synsets:
        # Get base name
        base_name = s.name().split('.')[0].upper()
        # Clean naming
        if '_' in base_name or '-' in base_name:
            continue
            
        lemmas = set()
        for lemma in s.lemmas():
            name = lemma.name().replace('_', ' ')
            lemmas.add(name)
            lemmas.add(name + "s")
            lemmas.add(name + "ed")
            lemmas.add(name + "ing")
            
        alias_str = ", ".join(list(lemmas)[:20]) # Limit to 20 aliases max
        
        block = f"""
■ JCROSS_LEXICON_VERB_{base_name}
【空間座相】
[重:5.0] [時:1.0] [核:1.0]
【連帯】
Subject:Entity:1.0
Object:Entity:1.0
Alias:{alias_str}
"""
        out_blocks.append(block.strip())
        total_generated += 1
        
        if total_generated >= 1000:
            break
            
    with open(lexicon_file, "a", encoding="utf-8") as f:
        f.write("\n\n" + "\n\n".join(out_blocks) + "\n")
        
    print(f"🎉 Lexicon Forge Complete. Added exactly {total_generated} verbs to Core Lexicon without any LLM calls.")

if __name__ == "__main__":
    run_lexicon_forge()
