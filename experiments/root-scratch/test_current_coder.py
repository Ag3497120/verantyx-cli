import sys
import os
import torch
from cli.scripts.telepathic_coder import TelepathicCoder

def main():
    print("Initializing Telepathic Coder (Lossless, Full Local Inference)...")
    coder = TelepathicCoder(workspace_dir="/Users/motonishikoudai/verantyx-cli", cluster_mode=None)
    
    # Create a dummy intent vector (representing the Swarm's telepathic consensus)
    dummy_vector = torch.randn(1, 3840).to(torch.float16)
    
    # The prompt explicitly given by the system
    context_prompt = "Context: Create an advanced command-line calculator application in Python."
    
    print("\n--- Running Code Synthesis (Testing Python Switchable Brain) ---")
    output = coder.synthesize_code(dummy_vector, subtask_prompt=context_prompt)
    
    print("\n--- Output ---")
    print(output)
    
    print("\n--- Analysis ---")
    print("If the Lossless Healer worked, this should output perfect Python code without word salad.")

if __name__ == "__main__":
    main()
