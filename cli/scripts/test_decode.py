import torch
import sys
import os

# Ensure the cli scripts directory is in the path so we can import verantyx_shell
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'cli', 'scripts'))

from verantyx_shell import CommanderLanguageInterface

def main():
    print(f"  [\033[36mTest\033[0m] Initializing Commander Language Interface for Decoding Test...")
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    
    # Initialize the interface (loads Gemma-4-12B tokenizer and model for decoding)
    commander = CommanderLanguageInterface(target_dim=3840, device=device)
    
    print(f"\n  [\033[36mTest\033[0m] Generating a synthetic intent vector (simulating Scout output)...")
    # Simulate a vector that has passed through JCross SVD layers
    torch.manual_seed(42)
    # Using float16 to match the model's expected input
    synthetic_vector = torch.randn(1, 1, 3840, dtype=torch.float16, device=device)
    
    print(f"  [\033[36mTest\033[0m] Initiating Decode Process (Approach C: Prefix Injection)...")
    
    # Decode the vector
    response_text = commander.decode(synthetic_vector)
    
    print(f"\n" + "="*50)
    print(f"[\033[35mVerantyx AI (Test Output)\033[0m]")
    print(f"{response_text}")
    print(f"="*50 + "\n")
    
    if "33302:" in response_text or "1:1:1" in response_text:
        print(f"  [\033[31mFAIL\033[0m] Representation Degeneration (Degenerative loop) detected.")
    else:
        print(f"  [\033[32mSUCCESS\033[0m] Text generation executed without degeneration loop.")

if __name__ == "__main__":
    main()
