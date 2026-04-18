import re
import nltk
from typing import List, Dict, Any

# Ensure basic NLTK components exist globally once
try:
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('maxent_ne_chunker', quiet=True)
    nltk.download('words', quiet=True)
except:
    pass

class PureCPUSymbolicExtractor:
    """
    Extremely fast O(1) Lexical Parsing Engine that converts raw text into
    JCross Memory Fragments without relying on LLMs.
    Uses POS (Part-of-Speech) tagging to isolate Entity -> Verb -> Entity relationships.
    """
    @staticmethod
    def extract_fragments(evidence_text: str) -> List[Dict[str, Any]]:
        fragments = []
        if not evidence_text or not evidence_text.strip():
            return fragments
            
        # Split text into manageable chunks so we know the context
        blocks = evidence_text.split("--- Chunk")
        
        frag_id_counter = 1
        
        for block in blocks:
            if not block.strip():
                continue
                
            # Naive sentence split by period (to be ultra fast)
            sentences = [s.strip() for s in re.split(r'[.!?\n]', block) if len(s.strip()) > 10]
            
            for sent_idx, sentence in enumerate(sentences):
                # Basic Tokenization
                try:
                    words = nltk.word_tokenize(sentence)
                    tagged = nltk.pos_tag(words)
                except Exception:
                    # Fallback if NLTK data isn't perfectly configured
                    words = sentence.split()
                    tagged = [(w, 'NN') for w in words] # Fake tags
                    
                # We want a [Noun Phrase] -> [Verb Phrase] -> [Noun/Adj Phrase] model
                subjects = []
                verbs = []
                objects = []
                
                state = 0 # 0=Subject gathering, 1=Verb gathering, 2=Object gathering
                
                for word, tag in tagged:
                    # Simple heuristic
                    if state == 0:
                        if tag.startswith('VB'):  # Hit a verb!
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
                        # Append the rest to object
                        if tag.startswith('VB'):
                            # Another verb block in the sentence? Ignore or reset, let's keep it simple and just append
                            objects.append(word)
                        elif tag.startswith('NN') or tag.startswith('JJ') or tag.startswith('CD') or tag.startswith('IN'):
                            # Only specific pos to object
                            objects.append(word)
                
                sub_str = " ".join(subjects)
                verb_str = " ".join(verbs)
                obj_str = " ".join(objects)
                
                # If we got a valid sub and obj
                if len(sub_str) > 0 and len(obj_str) > 0:
                    fragments.append({
                        "subject": sub_str,
                        "predicate": verb_str if len(verb_str) > 0 else "[同]",
                        "object": obj_str,
                        "context": sentence,
                        "state": "確定",
                        "source": "PureCPUExtractor"
                    })
                    frag_id_counter += 1
                else:
                    # If parsing failed softly, let's fallback to semantic half-extraction
                    # which still helps the puzzle engine constraint matching!
                    # Example: The entire sentence is just "Bob."
                    fragments.append({
                        "subject": sentence[:50],
                        "predicate": "[同]",
                        "object": sentence[-50:],
                        "context": sentence,
                        "state": "確定",
                        "source": "PureCPUExtractor_Fallback"
                    })
                    
        return fragments
