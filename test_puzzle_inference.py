import time
from verantyx.cross_simulator.puzzle_inference import PuzzleInferenceEngine

def test_puzzle():
    # Simulated fragments extracted by the lightweight 2B model
    fragments = [
        {
            "state": "確定",
            "subject": "UCLA",
            "predicate": "Attended_for_undergrad",
            "object": "2010 to 2014",
            "source": "idx_305"
        },
        {
            "state": "確定",
            "subject": "John Doe",
            "predicate": "Works_at",
            "object": "Google Mountain View",
            "source": "idx_12"
        },
        {
            "state": "確定",
            "subject": "Admon",
            "predicate": "works",
            "object": "Sunday",
            "source": "idx_5"
        },
        {
            "state": "確定",
            "subject": "Admon",
            "predicate": "shift_rotation",
            "object": "8 am - 4 pm",
            "source": "idx_5"
        },
        {
            "state": "操作",
            "subject": "cup of joe",
            "predicate": "[同]",
            "object": "iced americano",
            "source": "JCrossOpLexicon"
        },
        {
            "state": "確定",
            "subject": "John",
            "predicate": "purchased",
            "object": "iced americano",
            "source": "idx_1"
        }
    ]
    
    # Init the pure Python Symbolic Engine
    start_time = time.time()
    engine = PuzzleInferenceEngine(fragments)
    
    # 1. Forward Question
    q1 = "When did I attend UCLA?"
    ans1 = engine.solve(q1)
    print(f"Q: {q1}")
    print(f"A: {ans1}")
    
    # 2. Reverse Question
    q2 = "Who works at Google Mountain View?"
    ans2 = engine.solve(q2)
    print(f"Q: {q2}")
    print(f"A: {ans2}")
    
    # 3. Multi-Hop Question
    q3 = "What was the rotation for Admon on a Sunday?"
    ans3 = engine.solve(q3)
    print(f"Q: {q3}")
    print(f"A: {ans3}")

    # 4. Operational Command (Nuance) Question
    q4 = "What kind of cup of joe did John get?"
    ans4 = engine.solve(q4)
    print(f"Q: {q4}")
    print(f"A: {ans4}")
    
    end_time = time.time()
    
    print(f"---\nTotal CPU Time (Init + 4 Solves): {(end_time - start_time):.5f} seconds")

if __name__ == "__main__":
    test_puzzle()
