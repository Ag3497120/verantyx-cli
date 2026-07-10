import os
import sys
import torch

# Ensure we can import from cli/scripts
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telepathic_coder import TelepathicCoder

def main():
    print("[*] Testing Telepathic Coder (Commander) with Optimal Healed Weights...")
    workspace_dir = os.getcwd()
    
    coder = TelepathicCoder(workspace_dir, cluster_mode='master')
    
    # We used intent_id = 2 for the Timer App Code in optimal healing
    print("\n[*] Generating telepathic intent vector (Timer App Code)...")
    intent_vector = torch.ones((1, 3840), dtype=torch.float32) * 2
    
    prompt = "Based on the exact plan below, write the Swift code:\n1. Initialize a SwiftUI View.\n2. Create state variables for time and running status.\n3. Add a Timer publisher.\n4. Display the formatted time and control buttons.\n# Code:\n"
    
    print(f"[*] Invoking Coder Synthesis Phase...")
    edited_code = coder._run_decoding_phase(intent_vector, sys_prompt=prompt)
    
    print("\n==================================================")
    print(" [Commander Generated Swift Code]")
    print("==================================================")
    print(edited_code)
    print("==================================================")
    
    if hasattr(coder.brain, 'close'):
        coder.brain.close()

if __name__ == "__main__":
    main()
