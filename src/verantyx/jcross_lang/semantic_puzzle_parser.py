import re
import os
from typing import List, Dict

class GrammarPuzzleEngine:
    """
    Pure CPU constraint solver for Natural Language Processing.
    Treats grammar extraction as a JCross topological puzzle, bypassing Neural extraction.
    """
    
    def __init__(self, lexicon_path: str = None):
        self.verb_constraints = {}
        self.noun_aliases = {}
        self._load_lexicon(lexicon_path)
        
    def _load_lexicon(self, path: str):
        if not path or not os.path.exists(path):
            # Hardcoded fallbacks if no file is found (for unit tests / bootstrapping)
            self.verb_constraints = {
                "attend": {"alias": ["went to", "studied at"], "relation": "Attended"},
                "work": {"alias": ["employed by", "worked at"], "relation": "Works_at"}
            }
            self.noun_aliases = {
                "i": "User", "my": "User", "mine": "User", "myself": "User"
            }
            return
            
        # Optional: Load directly from `.jcross` file
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            current_node = None
            for line in lines:
                line = line.strip()
                if line.startswith("■ JCROSS_LEXICON_VERB_"):
                    current_node = line.replace("■ JCROSS_LEXICON_VERB_", "").lower()
                    self.verb_constraints[current_node] = {"alias": [], "relation": current_node.capitalize()}
                elif line.startswith("Alias:") and current_node:
                    aliases = line.replace("Alias:", "").split(",")
                    self.verb_constraints[current_node]["alias"].extend([x.strip() for x in aliases])
                    
    def _normalize(self, text: str) -> str:
        text = text.lower()
        # Basic punctuation clean
        return re.sub(r'[^\w\s]', '', text)

    def extract_triples(self, block_text: str, source_id: str = "raw") -> List[Dict]:
        """
        Takes raw english text and extracts the core topological meaning 
        as JCross Fragments without any LLM inference speed limits.
        """
        fragments = []
        sentences = [s.strip() for s in re.split(r'[.!?]', block_text) if s.strip()]
        
        for sent in sentences:
            norm_sent = self._normalize(sent)
            words = norm_sent.split()
            
            # Simple Constraint Flow: Subj -> Verb -> Obj
            # 1. Finding Verb Core
            core_verb = None
            verb_relation = None
            verb_idx = -1
            
            for v_key, v_data in self.verb_constraints.items():
                # Direct match
                if v_key in words:
                    core_verb = v_key
                    verb_relation = v_data["relation"]
                    verb_idx = words.index(v_key)
                    break
                # Alias match
                for alias in v_data.get("alias", []):
                    if alias in norm_sent:
                        core_verb = alias
                        verb_relation = v_data["relation"]
                        # approximation
                        verb_idx = norm_sent.split().index(alias.split()[0]) 
                        break
                if core_verb:
                    break
                    
            if core_verb and verb_idx != -1:
                # 2. Extract Subject (Left of Verb)
                subject_chunk = " ".join(words[:verb_idx])
                # Resolve Identity
                subject = self.noun_aliases.get(subject_chunk, subject_chunk).capitalize()
                
                # 3. Extract Object (Right of Verb)
                object_chunk = " ".join(words[verb_idx+len(core_verb.split()):])
                obj = object_chunk.capitalize()
                
                if subject and obj:
                    fragments.append({
                        "state": "確定",
                        "subject": subject,
                        "predicate": verb_relation,
                        "object": obj,
                        "source": source_id
                    })
                        
        return fragments
