import re
import nltk
from typing import List, Dict, Any, Tuple

try:
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except:
    pass

class SemanticIngestionEngine:
    """
    Ingests raw text and generates JCross Conceptual Mapping Operations (OP.MAP)
    instead of storing raw strings. This creates a purely mathematical topology.
    """
    def __init__(self):
        self.concept_counter = 1
        self.relation_counter = 1
        # Operations mapping table equivalent to OP.MAP commands: ID -> Raw String
        self.mapping_table: Dict[str, str] = {}
        
    def _get_concept_id(self, raw_string: str) -> str:
        # Prevent duplicate identical strings having different IDs locally
        for k, v in self.mapping_table.items():
            if v == raw_string and k.startswith("CONCEPT_"):
                return k
                
        c_id = f"CONCEPT_{self.concept_counter}"
        self.mapping_table[c_id] = raw_string
        self.concept_counter += 1
        return c_id
        
    def _get_relation_id(self, raw_string: str) -> str:
        for k, v in self.mapping_table.items():
            if v == raw_string and k.startswith("RELATION_"):
                return k
                
        r_id = f"RELATION_{self.relation_counter}"
        self.mapping_table[r_id] = raw_string
        self.relation_counter += 1
        return r_id

    def extract_conceptual_fragments(self, evidence_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        fragments = []
        if not evidence_text or not evidence_text.strip():
            return fragments, self.mapping_table
            
        blocks = evidence_text.split("--- Chunk")
        
        for block in blocks:
            if not block.strip():
                continue
                
            sentences = [s.strip() for s in re.split(r'[.!?\n]', block) if len(s.strip()) > 10]
            
            for sentence in sentences:
                try:
                    words = nltk.word_tokenize(sentence)
                    tagged = nltk.pos_tag(words)
                except Exception:
                    words = sentence.split()
                    tagged = [(w, 'NN') for w in words] 
                    
                subjects, verbs, objects = [], [], []
                state = 0
                
                for word, tag in tagged:
                    if state == 0:
                        if tag.startswith('VB'):  
                            verbs.append(word)
                            state = 1
                        elif tag.startswith('NN') or tag.startswith('JJ') or tag.startswith('PRP') or tag.startswith('CD'):
                            subjects.append(word)
                    elif state == 1:
                        if tag.startswith('VB'):
                            verbs.append(word)
                        elif tag.startswith('NN') or tag.startswith('JJ') or tag.startswith('PRP') or tag.startswith('CD'):
                            objects.append(word)
                            state = 2
                    elif state == 2:
                        if tag.startswith('VB'):
                            objects.append(word)
                        elif tag.startswith('NN') or tag.startswith('JJ') or tag.startswith('CD') or tag.startswith('IN'):
                            objects.append(word)
                
                sub_str = " ".join(subjects)
                verb_str = " ".join(verbs)
                obj_str = " ".join(objects)
                
                # Dynamic OP.MAP logic:
                if len(sub_str) > 0 and len(obj_str) > 0:
                    c_sub = self._get_concept_id(sub_str)
                    c_obj = self._get_concept_id(obj_str)
                    r_pred = self._get_relation_id(verb_str if len(verb_str) > 0 else "[同]")
                    
                    fragments.append({
                        "subject": c_sub,
                        "predicate": r_pred,
                        "object": c_obj,
                        "context": sentence, 
                        "state": "確定",
                        "source": "SemanticIngestionEngine"
                    })
                else:
                    c_sub = self._get_concept_id(sentence[:50])
                    c_obj = self._get_concept_id(sentence[-50:])
                    r_pred = self._get_relation_id("[同]")
                    
                    fragments.append({
                        "subject": c_sub,
                        "predicate": r_pred,
                        "object": c_obj,
                        "context": sentence,
                        "state": "確定",
                        "source": "SemanticIngestionEngine_Fallback"
                    })
                    
        return fragments, self.mapping_table
