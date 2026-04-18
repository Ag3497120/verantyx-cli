import json
import time
import uuid
from nltk.corpus import wordnet as wn

def clean_word(word_str):
    return word_str.replace("_", " ").lower()

def forge_lexicon(output_file="omega_lexicon.jsonl"):
    print("Molding Semantic Edges from WordNet into JCross Operations...")
    start_time = time.time()
    
    # Using a set to prevent exact duplicate edges
    unique_edges = set()
    total_edges = 0
    exported_entries = []

    def emit_edge(source, predicate, target):
        nonlocal total_edges
        edge_id = f"{source}|{predicate}|{target}"
        if edge_id not in unique_edges:
            unique_edges.add(edge_id)
            total_edges += 1
            exported_entries.append({
                "__id__": f"MEGA_{uuid.uuid4().hex[:12]}",
                "state": "操作",
                "subject": source,
                "predicate": predicate,
                "object": target,
                "source": "WordNet_Omega"
            })
            
            # Periodically write to save memory if needed, but doing it in memory is fine for 1M
            if len(exported_entries) >= 500_000:
                flush_to_disk()
                
    def flush_to_disk():
        nonlocal exported_entries
        with open(output_file, "a", encoding="utf-8") as f:
            for entry in exported_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        exported_entries.clear()

    # Clear previous file
    open(output_file, "w").close()

    synsets = list(wn.all_synsets())
    for s in synsets:
        lemmas = s.lemmas()
        
        # 1. Synonyms (同) - All words in the same synset mean the same
        for l1 in lemmas:
            w1 = clean_word(l1.name())
            for l2 in lemmas:
                w2 = clean_word(l2.name())
                if w1 != w2:
                    emit_edge(w1, "[同]", w2)

        # 2. Antonyms (反)
        for l in lemmas:
            w1 = clean_word(l.name())
            for ant in l.antonyms():
                w2 = clean_word(ant.name())
                emit_edge(w1, "[反]", w2)
                emit_edge(w2, "[反]", w1)

        # 3. Hypernyms (親) and Hyponyms (子)
        for hyper in s.hypernyms():
            for hw in hyper.lemma_names():
                hw_clean = clean_word(hw)
                for l in lemmas:
                    sw = clean_word(l.name())
                    emit_edge(sw, "[親]", hw_clean)
                    emit_edge(hw_clean, "[子]", sw) # Inverse
                    
        # 4. Holonyms (全体) and Meronyms (部)
        for holo in s.member_holonyms() + s.part_holonyms() + s.substance_holonyms():
            for hw in holo.lemma_names():
                hw_clean = clean_word(hw)
                for l in lemmas:
                    sw = clean_word(l.name())
                    emit_edge(sw, "[全]", hw_clean)
                    emit_edge(hw_clean, "[部]", sw) # Inverse
                    
    # Final flush
    flush_to_disk()
    
    elapsed = time.time() - start_time
    print(f"✅ Lexicon Forge Complete!")
    print(f"   Time elapsed: {elapsed:.2f} seconds")
    print(f"   Total Unique Operating Nodes Forged: {total_edges:,}")

if __name__ == "__main__":
    forge_lexicon()
