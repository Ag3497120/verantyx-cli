import time
import os
from src.verantyx.jcross_lang.semantic_puzzle_parser import GrammarPuzzleEngine

def test_semantic_parsing():
    # Provide the path to the declarative lexicon
    lexicon_path = os.path.join(os.path.dirname(__file__), "src", "verantyx", "knowledge_base", "core_lexicon.jcross")
    
    print(f"Loading Lexicon from: {lexicon_path}")
    engine = GrammarPuzzleEngine(lexicon_path)
    
    test_sentences = [
        "I attended UCLA from 2010 to 2014.",
        "My friend worked at Google Mountain View last year."
    ]
    
    start_time = time.time()
    
    print("\n--- Semantic Puzzle Extraction Results ---")
    for st in test_sentences:
        print(f"Raw Text: '{st}'")
        fragments = engine.extract_triples(st, source_id="mock_chunk_1")
        for f in fragments:
            print(f"  -> Extracted Triple: ({f['subject']}) -> [{f['predicate']}] -> ({f['object']})")
            
    end_time = time.time()
    print(f"\nTotal Parsing Time (CPU ONLY): {(end_time - start_time):.5f} seconds")

if __name__ == "__main__":
    test_semantic_parsing()
