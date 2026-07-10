import os
import sys
import torch

# Ensure we can import from cli/scripts
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telepathic_coder_experimental import TelepathicCoder
from bucket_relay_swarm_experimental import JCrossBrain

def main():
    print("[*] Testing Ambient Telepathy B Pipeline (Qwen Prism Translation)...")
    workspace_dir = os.getcwd()
    
    coder = TelepathicCoder(workspace_dir, cluster_mode='master')
    jgen_path = os.path.join(workspace_dir, "cli", "telepathic_coder_lossless.jgen")
    if not os.path.exists(jgen_path):
        jgen_path = os.path.join(workspace_dir, "telepathic_coder_lossless.jgen")
        if not os.path.exists(jgen_path):
            jgen_path = os.path.join(workspace_dir, "cli", "gemma_12b_generative.jgen")
    brain = JCrossBrain(jgen_path)
    
    # 1. Simulate Worker debating and drifting (think_internally generates latent vectors)
    print("\n[*] Simulating Worker thought process (Internal Drift Prevention)...")
    # For test simplicity, we just use the first step of the thought loop directly
    # Assuming standard dimension (e.g., 3840 for intent, we create a dummy state)
    dummy_input_vector = torch.randn(1, 3840, dtype=torch.float32)
    # Callback to represent Coder verification at each step
    def coder_verify_callback(current_vector, step):
        print(f"\n[Telepathic Coder] Verifying Worker thought at step {step}...")
        # Coder maps the vector to Qwen dictionary to get a design vector
        verified_vector = coder.verify_and_translate_latent(current_vector)
        return verified_vector

    final_state = brain.think_internally(
        ambient_context=dummy_input_vector,
        thought_steps=2,
        step_callback=coder_verify_callback
    )
    
    print("\n[*] Final converged Worker state obtained:", final_state.shape)
    
    # 2. Let coder synthesize code using the final illuminated knowledge
    print("\n[*] Synthesizing final code from Worker intent...")
    prompt = "Please output the verified design implementation."
    edited_code = coder._run_decoding_phase(final_state, sys_prompt=prompt)
    
    print("\n==================================================")
    print(" [Gemma Coder Generated Blueprint]")
    print("==================================================")
    print(edited_code)
    print("==================================================")
    
    if hasattr(coder.brain, 'close'):
        coder.brain.close()
    if hasattr(brain, 'close'):
        brain.close()

if __name__ == "__main__":
    main()
