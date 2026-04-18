import re
from typing import List, Dict, Optional, Set
import time
from collections import defaultdict

class PuzzleInferenceEngine:
    """
    Native Puzzle Inference Engine (CPU-only Symbolic Solver).
    Translates non-deterministic LLM evaluation into deterministic
    Sub-Graph Topological Matching in 0.01 seconds.
    """
    def __init__(self, fragments: List[Dict]):
        # Graph: Subject -> List[(Predicate, Object, Source, TimeIdx)]
        # Graph keeps directional edges
        self.graph = defaultdict(list)
        # Reverse Graph: Object -> List[(Predicate, Subject, Source, TimeIdx)]
        self.reverse_graph = defaultdict(list)
        
        # The Operational Command Core (O(1) Nuance Traversal)
        self.operations = defaultdict(lambda: defaultdict(set))
        
        # Dead End Tracking (for Simulator Visualization)
        self.dead_ends = []
        
        # Build the Triple Graph & Parse Operation Commands
        for frag in fragments:
            if frag.get("state") == "操作":
                # Handle Operations like [同], [親], [反]
                source_word = str(frag.get("subject", "")).strip().lower()
                target_word = str(frag.get("object", "")).strip().lower()
                predicate = str(frag.get("predicate", "")).strip()
                if source_word and target_word and predicate:
                    self.operations[source_word][predicate].add(target_word)
            elif frag.get("state") == "確定":
                sub = str(frag.get("subject", "") or "").strip()
                pred = str(frag.get("predicate", "") or "").strip()
                obj = str(frag.get("object", "") or "").strip()
                source = str(frag.get("source", "") or "")
                time_idx = float(frag.get("time_idx", 0.0))
                
                if sub and pred and obj:
                    self.graph[sub].append((pred, obj, source, time_idx))
                    self.reverse_graph[obj].append((pred, sub, source, time_idx))

    def _clean_token(self, text: str) -> str:
        return re.sub(r'[^\w\s\-\']', '', text).strip()

    def _tokenize(self, text: str) -> Set[str]:
        """Extremely fast, naive tokenization for string overlap heuristics."""
        text = text.lower()
        # Remove punctuation
        text = self._clean_token(text)
        stopwords = {"what", "who", "when", "where", "why", "how", "is", "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "of", "did", "does", "do", "are", "was", "were", "my", "i", "me", "he", "she", "it", "they", "them"}
        return {word for word in text.split() if word not in stopwords and len(word) > 1}

    def solve(self, question: str, syn_w: float = 0.9, hyp_w: float = 0.5, hol_w: float = 0.3) -> Optional[str]:
        """
        Attempts to solve the question symbolically via exact graph traversal.
        Utilizes pre-loaded O(1) Operation Commands to map vague phrases 
        with Dimensional Weight Scaling (TF-IDF style semantic gravity).
        """
        raw_q_tokens = self._tokenize(question)
        if not raw_q_tokens:
            return None
            
        q_tokens = {tok: 1.0 for tok in raw_q_tokens}
        
        # [OPERATION COMMAND EXPANSION LAYER]
        # Detect multi-word slang & map to hard tokens before matching
        # Generate unigrams, bigrams, trigrams from question to match slang
        words = question.lower().split()
        ngrams = []
        for n in range(1, min(4, len(words) + 1)):
            for i in range(len(words) - n + 1):
                ngrams.append(" ".join(words[i:i+n]))
                
        def _inject_weight(target_words, weight):
            for target in target_words:
                tokens = self._tokenize(target)
                for t in tokens:
                    q_tokens[t] = max(q_tokens.get(t, 0.0), weight)

        def apply_operations(source: str):
            ops = self.operations.get(source)
            if not ops: return
            
            # [同] Synonyms: Functional equivalent (syn_w weight)
            if "[同]" in ops:
                _inject_weight(ops["[同]"], syn_w)
            
            # [親] Hypernyms / [子] Hyponyms: Conceptual overlap (hyp_w weight)
            for rel in ["[親]", "[子]"]:
                if rel in ops:
                    _inject_weight(ops[rel], hyp_w)

            # [全] Holonyms / [部] Meronyms: Partial associative overlap (hol_w weight)
            for rel in ["[全]", "[部]"]:
                if rel in ops:
                    _inject_weight(ops[rel], hol_w)

        for ngram in ngrams:
            apply_operations(ngram)
            clean_tok = self._clean_token(ngram) # fallback
            if clean_tok != ngram:
                apply_operations(clean_tok)

        best_match_score = 0
        best_candidate_obj = None
        
        # We need to accumulate objects if multiple edges match equally well
        candidate_pool = defaultdict(set)
        
        # Helper for weighted overlap
        def calculate_overlap(tokens_set):
            return sum(q_tokens.get(tok, 0.0) for tok in tokens_set)
        
        # Strategy 1: Forward Traversal 
        for subject, edges in self.graph.items():
            sub_tokens = self._tokenize(subject)
            if not sub_tokens:
                continue
                
            overlap = calculate_overlap(sub_tokens)
            if overlap > 0:
                for pred, obj, _, time_idx in edges:
                    pred_tokens = self._tokenize(pred)
                    score = overlap + (0.5 * calculate_overlap(pred_tokens))
                    # ⏳ Temporal/Priority Bonus (Chronological State Shift Horizon)
                    score += (time_idx * 0.05)
                    
                    if score > 0:
                        candidate_pool[score].add(obj)
                        
                    if score > best_match_score and obj.lower() not in {"here's", "assistant", "user", "i", "we", "you", "it", "they"}:
                        best_match_score = score
                        best_candidate_obj = obj
                        
                # MULTI-HOP Traversal (Depth=2)
                for p1, obj1, _, t1 in edges:
                    obj1_toks = self._tokenize(obj1)
                    if calculate_overlap(obj1_toks) > 0:
                        for p2, obj2, _, t2 in edges:
                            if p1 == p2 and obj1 == obj2:
                                continue
                            p2_toks = self._tokenize(p2)
                            score = overlap + (0.5 * calculate_overlap(p2_toks)) + 1.0 + (t2 * 0.05)
                            if score > best_match_score and obj2.lower() not in {"here's", "assistant", "user", "i", "we", "you", "it", "they"}:
                                best_match_score = score
                                best_candidate_obj = obj2
                        
        # Strategy 2: Reverse Traversal
        for obj_node, edges in self.reverse_graph.items():
            obj_tokens = self._tokenize(obj_node)
            if not obj_tokens:
                continue
                
            overlap = calculate_overlap(obj_tokens)
            if overlap > 0:
                for pred, sub, _, time_idx in edges:
                    pred_tokens = self._tokenize(pred)
                    score = overlap + (0.5 * calculate_overlap(pred_tokens))
                    score += (time_idx * 0.05)
                    
                    if score > 0:
                        candidate_pool[score].add(sub)
                    
                    if score > best_match_score and sub.lower() not in {"here's", "assistant", "user", "i", "we", "you", "it", "they"}:
                        best_match_score = score
                        best_candidate_obj = sub
                        
        if candidate_pool:
            # Get the top 3 highest scores
            sorted_scores = sorted(candidate_pool.keys(), reverse=True)
            top_scores = sorted_scores[:3]
            
            # Gather all objects from those top scores
            top_candidates = []
            for s in top_scores:
                top_candidates.extend(list(candidate_pool[s]))
                
            # Filter out generic conversation elements and remove duplicates without losing order
            seen = set()
            filtered_candidates = []
            for c in top_candidates:
                c_clean = str(c).strip().lower()
                if c_clean not in {"here's", "assistant", "user", "i", "we", "you", "it", "they", "yes", "no", "sure", "of course"} and len(c_clean) > 2:
                    if c_clean not in seen:
                        seen.add(c_clean)
                        filtered_candidates.append(str(c).strip())
            
            if filtered_candidates:
                return ", ".join(filtered_candidates)
            else:
                self.dead_ends.append(f"Filtered out all candidates -> {top_candidates}")
                print(f"  [🧩 PUZZLE DEAD-END] Reached nodes but filtered out generic concepts.")
                return None
        
        self.dead_ends.append(f"Graph traversal yielded 0 candidate scores for question.")
        print(f"  [🧩 PUZZLE DEAD-END] No topological overlaps found.")
        return None
