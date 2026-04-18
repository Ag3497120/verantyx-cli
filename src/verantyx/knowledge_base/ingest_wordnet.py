import os
import nltk
from nltk.corpus import wordnet as wn

def download_wordnet():
    try:
        wn.ensure_loaded()
    except LookupError:
        print("Downloading NLTK WordNet dataset...")
        nltk.download('wordnet')
        wn.ensure_loaded()

def ingest_to_jcross(target_dir: str):
    download_wordnet()
    
    os.makedirs(target_dir, exist_ok=True)
    out_file = os.path.join(target_dir, "wordnet_full.jcross")
    
    print(f"Compiling full WordNet into {out_file}...")
    
    with open(out_file, "w", encoding="utf-8") as f:
        # We will iterate through verbs and nouns
        # For full scale, we do all_synsets. 
        synsets = list(wn.all_synsets())
        
        print(f"Total Synsets to Process: {len(synsets)}")
        
        for i, syn in enumerate(synsets):
            # Print progress every 10k
            if i % 10000 == 0:
                print(f"Processed {i} / {len(synsets)} nodes...")
                
            node_id = syn.name().replace("'", "_")
            
            f.write(f"■ JCROSS_WN_{node_id}\n")
            f.write("【空間座相】\n")
            
            # Simple gravity heuristic based on part of speech
            mass = 5.0 if syn.pos() == 'n' else (8.0 if syn.pos() == 'v' else 2.0)
            f.write(f"[重:{mass}] [空:1.0]\n")
            
            f.write("【連帯】\n")
            
            # Hypernyms (上位概念)
            for hyper in syn.hypernyms():
                h_name = hyper.name().replace("'", "_")
                f.write(f"WN_{h_name}:上位概念:1.0\n")
                
            # Hyponyms (下位概念)
            for hypo in syn.hyponyms():
                h_name = hypo.name().replace("'", "_")
                f.write(f"WN_{h_name}:下位概念:1.0\n")
                
            # Entailments (前提/帰結)
            for entail in syn.entailments():
                e_name = entail.name().replace("'", "_")
                f.write(f"WN_{e_name}:帰結:1.0\n")
                
            # Aliases / Lemmas
            lemmas = [lemma.name().replace('_', ' ') for lemma in syn.lemmas()]
            if lemmas:
                f.write(f"Alias:{','.join(lemmas)}\n")
                
            # Definition context
            f.write(f"Definition:{syn.definition()}\n\n")

    print(f"✅ Ingestion Complete! Saved out ~{len(synsets)} Spatial Nodes.")

if __name__ == "__main__":
    target = os.path.join(os.path.dirname(__file__), "ontologies")
    ingest_to_jcross(target)
