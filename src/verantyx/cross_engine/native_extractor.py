import re
import uuid
from typing import List, Dict, Any

class NativeExtractor:
    """
    Pure CPU Symbolic Extractor. 
    Eliminates the LLM bottleneck by ripping unstructured text into JCross Triplets
    using deterministic heuristic rule sets. Speed: > 10,000 sentences per second.
    """
    
    # Common English Stopwords
    STOPWORDS = {"the", "a", "an", "and", "or", "but", "if", "because", "as", "what", "which", "this", "that", "these", "those", "then", "just", "so", "than", "such", "both", "through", "about"}
    
    # Common Prepositions that often start objects or predicates
    PREPS = {"in", "on", "at", "to", "for", "with", "by", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "from", "up", "down"}

    @classmethod
    def _clean_token(cls, token: str) -> str:
        return re.sub(r'[^\w\s\-\']', '', token).strip()

    @classmethod
    def parse(cls, text: str) -> List[Dict[str, Any]]:
        fragments = []
        
        # 1. Split into sentences (handles punctuation and newlines)
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        
        for idx, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence or len(sentence) < 5:
                continue
                
            # Heuristic Rule 0: Markdown Table / Pipe-delimited Rows
            if '|' in sentence and sentence.count('|') >= 2:
                cells = [c.strip() for c in sentence.split('|') if c.strip() and not c.strip().startswith('---')]
                if len(cells) > 1:
                    row_header = cells[0]
                    for cell in cells[1:]:
                        fragments.append({
                            "__id__": f"NAT_{uuid.uuid4().hex[:8]}",
                            "state": "確定",
                            "subject": row_header,
                            "predicate": "contains",
                            "object": cell,
                            "source": f"sent_{idx}",
                            "raw_text": sentence,
                            "time_idx": idx
                        })
                    continue
                    
            # Heuristic Rule 1: Split on Verbs / Linking Words (is, was, has, purchased, went to)
            # A very blunt instrument: Split the sentence roughly into thirds.
            words = sentence.split()
            if len(words) < 3:
                continue
                
            # Build N-Grams manually to find Subjects and Objects avoiding stopwords
            sub_tokens = []
            pred_tokens = []
            obj_tokens = []
            
            state = "SUB"
            for word in words:
                clean_word = cls._clean_token(word)
                if not clean_word: continue
                
                lower_word = clean_word.lower()
                
                # Heuristic transition logic
                if state == "SUB":
                    if lower_word in {"is", "was", "are", "were", "has", "had", "will", "did", "does"} or (clean_word.endswith("ed") and len(clean_word) > 3) or (clean_word.endswith("s") and len(sub_tokens) > 0 and clean_word[0].islower()):
                        state = "PRED"
                        pred_tokens.append(clean_word)
                    else:
                        if lower_word not in cls.STOPWORDS:
                            sub_tokens.append(clean_word)
                elif state == "PRED":
                    # Predicates usually end when we hit nouns (capitalized) or prepositions indicating an object
                    if lower_word in cls.PREPS and len(pred_tokens) > 0:
                        pred_tokens.append(clean_word)
                        state = "OBJ"
                    elif lower_word not in {"is", "was", "has", "had", "been", "being"} and len(pred_tokens) > 0:
                        # Assuming the verb phrase ended
                        state = "OBJ"
                        if lower_word not in cls.STOPWORDS:
                            obj_tokens.append(clean_word)
                    else:
                        pred_tokens.append(clean_word)
                elif state == "OBJ":
                    if lower_word not in cls.STOPWORDS:
                        obj_tokens.append(clean_word)

            # Fallback for very simple sentences if parsing failed
            if not pred_tokens and len(words) >= 3:
                mid = len(words) // 2
                sub_tokens = words[:mid-1]
                pred_tokens = [words[mid-1]]
                obj_tokens = words[mid:]
                
            sub_str = " ".join(sub_tokens).strip()
            pred_str = " ".join(pred_tokens).strip()
            obj_str = " ".join(obj_tokens).strip()
            
            if sub_str and pred_str and obj_str:
                fragments.append({
                    "__id__": f"NAT_{uuid.uuid4().hex[:8]}",
                    "state": "確定",
                    "subject": " ".join(sub_tokens),
                    "predicate": " ".join(pred_tokens),
                    "object": " ".join(obj_tokens),
                    "source": f"sent_{idx}",
                    "raw_text": sentence,
                    "time_idx": idx
                })
                
        return fragments
