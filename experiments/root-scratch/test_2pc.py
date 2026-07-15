import os
import sys
import torch
from cli.scripts.two_phase_commit import execute_mediator_flow
from cli.scripts.chrono_memory import ChronoRegistry
from cli.scripts.verantyx_shell import ActionSpace
from cli.scripts.bucket_relay_swarm import TelepathicMemoryBank

def main():
    print("Running 2PC Mediator Test...")
    workspace = "/Users/motonishikoudai/verantyx-cli"
    target_file = os.path.join(workspace, "dummy_project/index.html")
    
    print("1. Initialize registries")
    chrono_registry = ChronoRegistry(workspace)
    memory_bank = TelepathicMemoryBank(os.path.join(workspace, "test.memory"))
    action_space = ActionSpace(device="cpu")
    
    print("2. Generate fake intent vector")
    intent_vector = action_space.encode_dummy("Test Edit Intent")
    
    print("3. Execute Mediator Flow")
    result = execute_mediator_flow(intent_vector, target_file, chrono_registry, action_space, memory_bank)
    
    if result:
        print("\nSUCCESS: Code was edited.")
        with open(target_file, "r") as f:
            print("File Content Tail:")
            print("\n".join(f.read().splitlines()[-5:]))
            
        print("\nChecking Registry:")
        latest_idx = chrono_registry.find_latest_for_file(target_file)
        print(f"Latest Index for {target_file}: {latest_idx}")
        if latest_idx is not None:
            entry = chrono_registry.get_entry(latest_idx)
            print(f"Entry Timestamp: {entry['timestamp']}")
            print(f"Entry Parent: {entry['transition_from']}")
    else:
        print("\nFAILED.")

if __name__ == "__main__":
    main()
