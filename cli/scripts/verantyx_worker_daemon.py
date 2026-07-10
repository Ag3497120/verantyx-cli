import os
import sys
import torch
import time
from thunderbolt_rpc import TensorTransferEngine
from bucket_relay_swarm import JCrossBrain
from matrix_ui import MatrixUIDecoder

def main():
    print("[\033[36mVerantyx Worker Daemon\033[0m] Starting up...")
    
    workspace_dir = os.getcwd()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(script_dir))
    
    # Load .jgen models (expecting them to be in the cli folder)
    worker_jgen = os.path.join(root_dir, "cli", "gemma_12b_generative.jgen")
    scout_jgen = os.path.join(root_dir, "cli", "commander_12b_rank1024.jgen")
    coder_jgen = os.path.join(root_dir, "cli", "telepathic_coder_lossless.jgen")
    if not os.path.exists(coder_jgen):
        # Fallback
        coder_jgen = worker_jgen
    
    if not os.path.exists(worker_jgen):
        print(f"[\033[31mError\033[0m] .jgen model not found at {worker_jgen}")
        sys.exit(1)
        
    print("[\033[36mWorker\033[0m] Loading JCrossBrain (.jgen)...")
    worker_brain = JCrossBrain(worker_jgen, device)
    scout_brain = JCrossBrain(scout_jgen, device)
    
    print("[\033[36mWorker\033[0m] Loading Distributed Coder Brain (Layers 246-328)...")
    coder_brain = JCrossBrain(coder_jgen, device, layer_start=246, layer_end=328)
    
    matrix_ui = MatrixUIDecoder()
    
    # Initialize RPC Server
    rpc = TensorTransferEngine(role='worker', host='0.0.0.0', port=5555)
    
    while True:
        try:
            rpc.start()  # Blocks until Master connects
            print("[\033[36mWorker\033[0m] Waiting for intent vector from Master...")
            
            while True:
                # 1. Receive intent vector from Master
                intent_vector = rpc.recv_tensor(dtype=torch.float16, shape=(1, 3840), device=device)
                if intent_vector is None:
                    print("[\033[33mWorker\033[0m] Master disconnected. Listening again...")
                    break  # Break inner loop, go back to rpc.start()
                    
                print("\n[\033[36mWorker\033[0m] Received intent vector. Starting Swarm Debate...")
                
                debate_vector = intent_vector.clone()
                
                # 2. Swarm Debate Loop (Worker nodes)
                for w_idx in range(1, 5):
                    prev_debate = debate_vector.clone()
                    if w_idx < 4:
                        role_name = f"Worker {w_idx}"
                        if w_idx == 2:
                            role_name = "Worker 2 (Search Crawler)"
                            
                        # Perform internal thinking
                        debate_vector, uncertainty = worker_brain.think_internally(debate_vector, thought_steps=20, role_name=role_name, color_code="\033[36m")
                        features = matrix_ui.record_step(role_name, debate_vector, prev_debate)
                        color_cyan = '\033[36m'
                        print(f"\n  {matrix_ui.render_terminal_progress(role_name, features, color_cyan)}")
                    else:
                        # Worker 4 (Coder Latent Alignment Mock - in worker it's just passing through or doing a final jgen pass)
                        role_name = "Worker 4 (Consensus Alignment)"
                        print(f"\n  [\033[94m{role_name}\033[0m] Entering Swarm Debate...")
                        debate_vector, uncertainty = worker_brain.think_internally(debate_vector, thought_steps=5, role_name=role_name, color_code="\033[94m")
                        features = matrix_ui.record_step(role_name, debate_vector, prev_debate)
                        color_blue = '\033[94m'
                        print(f"  {matrix_ui.render_terminal_progress(role_name, features, color_blue)}")
                
                # 3. Scout Execution Loop
                print(f"  [\033[35mScout\033[0m] Receiving Executable Latent and initiating Execution...")
                action_vector, _ = scout_brain.think_internally(debate_vector, thought_steps=15, role_name="Scout", color_code="\033[35m")
                features = matrix_ui.record_step("Scout", action_vector, debate_vector)
                color_magenta = '\033[35m'
                print(f"\n  {matrix_ui.render_terminal_progress('Scout', features, color_magenta)}")
                
                # 4. Send the final action vector back to Master
                print("[\033[36mWorker\033[0m] Sending final action vector back to Master...")
                rpc.send_tensor(action_vector)
                
                # 5. Enter Decoding Loop for Distributed Generation
                print("[\033[36mWorker\033[0m] Transitioning to Layer-wise Distributed Decoding (Layers 246-328)...")
                past_states = None
                while True:
                    # Receive intermediate tensor from Master during generation
                    hidden_state = rpc.recv_tensor(device=device)
                    if hidden_state is None:
                        print("[\033[33mWorker\033[0m] Master disconnected during decoding.")
                        break
                        
                    # Check for reset signal (dummy tensor)
                    if hidden_state.dim() == 3 and hidden_state.shape == (1, 1, 1):
                        past_states = None
                        rpc.send_tensor(torch.ones(1, 1, 1, device=device)) # Ack
                        continue
                        
                    # Process through second half of layers
                    if hidden_state is not None:
                        hidden_state, past_states = coder_brain.forward_latent(
                            hidden_state, 
                            past_states=past_states, 
                            role_name="WorkerNode", 
                            color_code="\033[36m"
                        )
                        # Send the processed tensor back to Master for token sampling
                        rpc.send_tensor(hidden_state)
                
        except KeyboardInterrupt:
            print("\n[\033[33mWorker\033[0m] Shutting down...")
            break
        except Exception as e:
            print(f"[\033[31mError\033[0m] {e}")
            import traceback
            traceback.print_exc()
            rpc.close()
            time.sleep(1)

    rpc.close()

if __name__ == "__main__":
    main()
