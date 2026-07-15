with open("cli/scripts/bucket_relay_swarm_9b.py", "r") as f:
    text = f.read()

archive_logic = """
    print(f"{C_SYS}  [Coder] Code synthesis complete in {time.time()-start_calc:.2f}s.{C_RESET}")
    
    # -----------------------------------------------------
    # ETERNAL MEMORY AUTO-ARCHIVING (KV CACHE EQUIVALENT)
    # -----------------------------------------------------
    print(f"\\n{C_SYS}=== Auto-Archiving Conversation into Eternal Memory ==={C_RESET}")
    # Encode User Input
    if user_input:
        user_vector = worker_brain.encode_text(user_input, worker_tokenizer).to(worker_brain.device)
        memory_bank.add_memory(user_vector, label=f"Chat User: {user_input[:20]}...", defer_save=True)
    
    # Encode Generated Code/Response
    if generated_code:
        response_vector = worker_brain.encode_text(generated_code, worker_tokenizer).to(worker_brain.device)
        memory_bank.add_memory(response_vector, label=f"Chat Agent: {generated_code[:20]}...", defer_save=True)
        
    memory_bank._save_to_ssd()
    print(f"{C_SYS}  [System] Successfully committed session to Eternal Memory.{C_RESET}")
"""

text = text.replace(
    '    print(f"{C_SYS}  [Coder] Code synthesis complete in {time.time()-start_calc:.2f}s.{C_RESET}")',
    archive_logic
)

with open("cli/scripts/bucket_relay_swarm_9b.py", "w") as f:
    f.write(text)
