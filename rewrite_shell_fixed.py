import sys, re

filename = '/Users/motonishikoudai/verantyx-cli/cli/scripts/verantyx_shell.py'
with open(filename, 'r') as f:
    content = f.read()

# 1. Add RPC Initialization
rpc_init = """    rpc = None
    if args.cluster_mode == 'master':
        print(f"{C_SYS}  [System] Initializing Thunderbolt RPC Client...{C_RESET}")
        from thunderbolt_rpc import TensorTransferEngine
        rpc = TensorTransferEngine(role='master', peer_ip=args.worker_ip, port=5555)
        rpc.start()
        
    intent_vector = global_coder.text_to_intent("Initial Boot Sequence")"""
content = re.sub(r'    intent_vector = global_coder\.text_to_intent\("Initial Boot Sequence"\)', rpc_init, content, count=1)

# 2. Extract block
start_marker = '            print(f"\\n[\\033[36mSYSTEM\\033[0m] Initiating Verantyx Flow...\\n")'
end_marker = '                    print(f"  [\\033[31mError\\033[0m] Coder Synthesis Failed: {e}")\n                    traceback.print_exc()'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx) + len(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Markers not found. start={start_idx}, end={end_idx}")
    sys.exit(1)

new_block = """            print(f"\\n[\\033[36mSYSTEM\\033[0m] Initiating Verantyx Flow...\\n")
            
            print(f"  [\\033[33mCommander\\033[0m] Breaking down task into manageable subtasks...")
            subtasks = global_coder.breakdown_task(user_input)
            print(f"  [\\033[33mCommander\\033[0m] Task broken down into {len(subtasks)} subtasks.")
            
            for subtask_idx, subtask in enumerate(subtasks):
                print(f"\\n============================================================")
                print(f"[\\033[36mSubtask {subtask_idx+1}/{len(subtasks)}\\033[0m] {subtask}")
                print(f"============================================================\\n")
                
                intent_vector = global_coder.text_to_intent(f"User Request: {subtask}")
                base_thought = intent_vector.clone()
                current_thought = intent_vector.clone()
                
                print(f"  [\\033[33mCommander\\033[0m] Comparing intent with Eternal Memory for Deep Insights...")
                current_thought = memory_bank.retrieve_memory(intent_vector)
                
                if mode_name == "Dynamic":
                    max_sim = calculate_similarity(intent_vector, memory_bank)
                    if max_sim < 0.85:
                        max_depth, threshold = 100, 0.50
                        print(f"  [\\033[35mDynamic Mode\\033[0m] Complex task detected (Sim: {max_sim:.2f}). Activating Deep Thinking...")
                    else:
                        max_depth, threshold = 10, 0.35
                        print(f"  [\\033[35mDynamic Mode\\033[0m] Familiar task detected (Sim: {max_sim:.2f}). Activating Quick Response...")
                else:
                    max_depth, threshold = default_depth, default_thresh
                    
                step_count = 0
                searches_performed = 0
                matrix_ui = MatrixUIDecoder()
                
                if args.cluster_mode == 'master' and rpc is not None:
                    print(f"  [\\033[36mThunderbolt RPC\\033[0m] Offloading Swarm Debate to Worker Node...")
                    intent_vector = global_coder.align_intent(intent_vector, original_prompt=subtask)
                    rpc.send_tensor(intent_vector)
                    print(f"  [\\033[36mThunderbolt RPC\\033[0m] Waiting for Worker to finish thinking...")
                    action_vector = rpc.recv_tensor(dtype=torch.float16, shape=(1, 3840), device=device)
                    if action_vector is None:
                        print(f"  [\\033[31mError\\033[0m] Worker disconnected.")
                        break
                else:
                    while step_count < max_steps:
                        step_count += 1
                        if max_steps > 1:
                            print(f"\\n  [\\033[33mSwarm Loop\\033[0m] Step {step_count}/{max_steps} started...")
                        
                        print(f"  [\\033[94mTelepathic Coder\\033[0m] Encoding Natural Language into Executable Latent Space and Diffusing...")
                        if step_count == 1:
                            intent_vector = global_coder.align_intent(intent_vector, original_prompt=subtask)
                        memory_bank.diffuse_thought(intent_vector, intensity=1.0, flag_label=f"Coder Target Intent (Step {step_count})", agent_id=94)
                        
                        if memory_bank.ambient_vector is not None:
                            telepathy_vectors = memory_bank.ambient_vector.unsqueeze(0)
                        elif memory_bank.zone_a_cache is not None:
                            telepathy_vectors = memory_bank.zone_a_cache[-5:].unsqueeze(0)
                        else:
                            telepathy_vectors = action_space.encode_dummy("Initial state").unsqueeze(0)
                        
                        print(f"  [\\033[36mWorkers\\033[0m] Catching Target Vector and Starting Telepathic Debate...")
                        debate_vector = current_thought.clone()
                        try:
                            worker_brain = JCrossBrain(worker_jgen, device)
                            for w_idx in range(1, 5):
                                prev_debate = debate_vector.clone()
                                
                                if w_idx < 4:
                                    role_name = f"Worker {w_idx}"
                                    if w_idx == 2:
                                        role_name = "Worker 2 (Search Crawler)"
                                    
                                    try:
                                        debate_vector, uncertainty = worker_brain.think_internally(debate_vector, thought_steps=20, role_name=role_name, color_code="\\033[36m")
                                        features = matrix_ui.record_step(role_name, debate_vector, prev_debate)
                                        print(f"\\n  {matrix_ui.render_terminal_progress(role_name, features, '\\033[36m')}")
                                    except Exception as e:
                                        print(f"  [\\033[31mError\\033[0m] Worker {w_idx} failed: {e}")
                                    
                                else:
                                    role_name = "Worker 4 (Telepathic Coder Latent Alignment)"
                                    print(f"\\n  [\\033[94mTelepathic Coder\\033[0m] Entering Swarm Debate as Node 4...")
                                    try:
                                        debate_vector, uncertainty = worker_brain.think_internally(debate_vector, thought_steps=5, role_name=role_name, color_code="\\033[94m")
                                        features = matrix_ui.record_step(role_name, debate_vector, prev_debate)
                                        print(f"  {matrix_ui.render_terminal_progress('Telepathic Coder', features, '\\033[94m')}")
                                        print(f"  [\\033[94mTelepathic Coder\\033[0m] Debate vector aligned towards Executable Latent Space.")
                                    except Exception as e:
                                        print(f"  [\\033[31mError\\033[0m] Latent Alignment Failed: {e}")
                                        
                            worker_brain.close()
                            del worker_brain
                            purge_memory()
                        except Exception as e:
                            import traceback
                            print(f"  [\\033[31mWorker Loop Error\\033[0m] Unexpected error in swarm debate loop: {e}")
                            traceback.print_exc()
                        worker_consensus = debate_vector.clone()
        
                        print(f"  [\\033[94mTelepathic Coder\\033[0m] Judging Workers' Consensus for Code Synthesizability...")
                        try:
                            coder_intent = global_coder.align_intent(worker_consensus, original_prompt=subtask)
                            features = matrix_ui.record_step("Telepathic Coder Judge", coder_intent, worker_consensus)
                            print(f"  {matrix_ui.render_terminal_progress('Telepathic Coder Judge', features, '\\033[94m')}")
                            
                            if features["convergence"] < 0.8:
                                print(f"  [\\033[94mTelepathic Coder\\033[0m] Consensus convergence is too low. Rejecting and passing intent back to loop...")
                                current_thought = coder_intent.clone()
                                continue
                            else:
                                print(f"  [\\033[94mTelepathic Coder\\033[0m] Consensus accepted. Latent structure is ready for decoding.")
                                action_vector = coder_intent.clone()
                        except Exception as e:
                            print(f"  [\\033[31mError\\033[0m] Coder Judgment Failed: {e}")
                            action_vector = worker_consensus.clone()
                            coder_intent = worker_consensus
                        
                        print(f"  [\\033[35mScout\\033[0m] Receiving Executable Latent and initiating Execution...")
                        try:
                            scout_brain2 = JCrossBrain(scout_jgen, device)
                            action_vector, _ = scout_brain2.think_internally(coder_intent, thought_steps=15, role_name="Scout", color_code="\\033[35m")
                            features = matrix_ui.record_step("Scout", action_vector, coder_intent)
                            print(f"\\n  {matrix_ui.render_terminal_progress('Scout', features, '\\033[35m')}")
                            scout_brain2.close()
                            del scout_brain2
                        except Exception as e:
                            print(f"  [\\033[31mError\\033[0m] Scout Execution Failed: {e}")
                            
                        break # End local swarm loop

                # --- Common Code Synthesis ---
                print(f"\\n============================================================")
                print(f"[\\033[95mVerantyx Code Synthesis\\033[0m] Handing over to Lossless Telepathic Coder")
                print(f"============================================================\\n")
                
                print(f"  [\\033[94mTelepathic Coder\\033[0m] Receiving final Executable Latent vector from Scout...")
                
                try:
                    # Determine final spatial intent of the vector before decoding
                    final_tool, final_sim = action_space.match_action(action_vector)
                    
                    # Coder uses its 30GB weights to decode the vector into text
                    inferred_code = global_coder.synthesize_code(action_vector, subtask_prompt=subtask)
                    
                    # Spatially decide if we should save this to a file
                    if final_tool == "discuss" or "```" not in inferred_code:
                        print(f"  [\\033[94mTelepathic Coder\\033[0m] Spatial intent resolved as Discussion (Anchor: {final_tool}). Skipping file synthesis.")
                    else:
                        ext = ".txt"
                        user_input_lower = user_input.lower()
                        if "c++" in user_input_lower or "cpp" in user_input_lower: ext = ".cpp"
                        elif "python" in user_input_lower or " py" in user_input_lower: ext = ".py"
                        elif "swift" in user_input_lower: ext = ".swift"
                        elif "javascript" in user_input_lower or " js" in user_input_lower: ext = ".js"
                        elif "typescript" in user_input_lower or " ts" in user_input_lower: ext = ".ts"
                        elif "rust" in user_input_lower: ext = ".rs"
                        elif "go" in user_input_lower or "golang" in user_input_lower: ext = ".go"
                        elif "html" in user_input_lower: ext = ".html"
                        
                        output_filename = f"verantyx_synthesis_task{subtask_idx+1}{ext}"
                        with open(os.path.join(workspace_dir, output_filename), "w") as f:
                            f.write(inferred_code)
                        print(f"  [\\033[94mTelepathic Coder\\033[0m] Decoding successful. Code written to: {output_filename}")
                        
                    purge_memory()
                except Exception as e:
                    import traceback
                    print(f"  [\\033[31mError\\033[0m] Coder Synthesis Failed: {e}")
                    traceback.print_exc()
                
                print("  [\\033[32mSwarm\\033[0m] Subtask declared complete. Moving to next subtask if any.")
                intent_vector = action_vector.clone()"""

content = content[:start_idx] + new_block + content[end_idx:]

with open(filename, 'w') as f:
    f.write(content)

print("Rewrite successful.")
