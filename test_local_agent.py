import time
from src.verantyx.mcp.local_agent import OllamaVerantyxAgent

def run_local_agent_test():
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
        }
    ]
    
    agent = OllamaVerantyxAgent(fragments)
    
    # Question 1: Nuance/Synonym Check
    q1 = "What kind of cup of joe did John get?"
    start_time = time.time()
    ans1 = agent.solve(q1)
    end_time = time.time()
    print(f"\nFinal Local Agent Output -> {ans1}")
    print(f"Time Taken: {(end_time - start_time):.2f}s\n")
    
    # Question 2: Multi-Hop Check
    q2 = "What was the rotation for Admon on a Sunday?"
    start_time = time.time()
    ans2 = agent.solve(q2)
    end_time = time.time()
    print(f"\nFinal Local Agent Output -> {ans2}")
    print(f"Time Taken: {(end_time - start_time):.2f}s\n")

if __name__ == "__main__":
    run_local_agent_test()
