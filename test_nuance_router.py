import time
from src.verantyx.cross_simulator.puzzle_inference import PuzzleInferenceEngine

def test_bidirectional_nuance():
    fragments = [
        {
            "state": "確定",
            "subject": "John",
            "predicate": "purchased",
            "object": "iced americano",
            "source": "idx_1"
        },
        {
            "state": "確定",
            "subject": "John",
            "predicate": "purchased",
            "object": "turkey sandwich",
            "source": "idx_1"
        }
    ]
    
    # Init the pure Python Symbolic Engine
    engine = PuzzleInferenceEngine(fragments)
    
    # Question with a vague nuance (slang/synonym) that isn't explicitly in the graph
    # "joe" means coffee.
    q = "What kind of cup of joe did he get?"
    
    start_time = time.time()
    ans = engine.solve(q)
    end_time = time.time()
    
    print(f"Q: {q}")
    print(f"A: {ans}")
    print(f"---\nTotal Process Time (Engine Miss -> LLM Nuance Dictionary): {(end_time - start_time):.3f} seconds")

if __name__ == "__main__":
    test_bidirectional_nuance()
