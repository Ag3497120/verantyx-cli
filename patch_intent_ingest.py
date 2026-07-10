import re

with open("cli/scripts/bucket_relay_swarm_9b.py", "r") as f:
    text = f.read()

# 1. Remove the old ingest_workspace definition
start_idx = text.find('def ingest_workspace(memory_bank, worker_brain, workspace_dir):')
if start_idx != -1:
    end_idx = text.find('if __name__ == "__main__":', start_idx)
    text = text[:start_idx] + text[end_idx:]

# 2. Insert the new sense_intent_and_ingest definition
intent_func = """
def sense_intent_and_ingest(memory_bank, worker_brain, workspace_dir, user_input, tokenizer):
    \"\"\"
    Intent-Driven Ingestion: Senses the user's intent and selectively loads only relevant
    files from the workspace into the Eternal Memory (acting as a true KV Cache).
    \"\"\"
    import os
    import glob
    
    if not user_input or not user_input.strip():
        return
        
    print(f"\\n{C_SYS}=== Intent-Driven KV Cache Ingestion ==={C_RESET}")
    print(f"{C_SYS}  [Commander] Sensing context requirements from user intent...{C_RESET}")
    
    # Extract potential keywords/filenames from user input
    words = set(user_input.replace(',', ' ').replace('.', ' ').split())
    target_files = set()
    
    search_pattern = os.path.join(workspace_dir, "**", "*")
    for file_path in glob.glob(search_pattern, recursive=True):
        if not os.path.isfile(file_path):
            continue
            
        rel_path = os.path.relpath(file_path, workspace_dir)
        filename = os.path.basename(file_path)
        
        # Skip hidden and cache dirs
        if any(part.startswith('.') for part in rel_path.split(os.sep)):
            continue
        if "__pycache__" in rel_path or "node_modules" in rel_path:
            continue
            
        # Very simple intent heuristic: if the filename or its base is mentioned in the prompt, ingest it!
        # Or if the file extension is specifically requested (e.g. 'python' -> load some .py files)
        base = filename.split('.')[0]
        if filename in words or base in words:
            target_files.add(file_path)
            
    if not target_files:
        print(f"{C_SYS}  [Commander] No specific file context required for this intent.{C_RESET}")
        return
        
    indexed_files = set()
    for item in memory_bank.zone_b_index:
        label = item.get("label", "")
        if label.startswith("File: "):
            indexed_files.add(label.replace("File: ", "").strip())
            
    count = 0
    for file_path in target_files:
        rel_path = os.path.relpath(file_path, workspace_dir)
        if rel_path in indexed_files:
            print(f"{C_SYS}  [System] {rel_path} is already in KV Cache.{C_RESET}")
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                continue
            if len(content) > 4000:
                content = content[:4000]
                
            formatted_text = f"File: {rel_path}\\nContent:\\n{content}"
            vector = worker_brain.encode_text(formatted_text, tokenizer).to(worker_brain.device)
            memory_bank.add_memory(vector, label=f"File: {rel_path}", defer_save=True)
            count += 1
            print(f"{C_SYS}  [System] Injected {rel_path} into KV Cache.{C_RESET}")
        except Exception as e:
            pass
            
    if count > 0:
        memory_bank._save_to_ssd()
        print(f"{C_SYS}  [System] Successfully committed {count} contextual files to Eternal Memory.{C_RESET}")

"""

text = text.replace('if __name__ == "__main__":', intent_func + '\nif __name__ == "__main__":')

# 3. Modify the main loop: remove indiscriminate call and add the intent call
text = text.replace(
'''    # -----------------------------------------------------
    # ETERNAL MEMORY INGESTION (PROJECT OMNISCIENCE)
    # -----------------------------------------------------
    ingest_workspace(memory_bank, worker_brain, workspace_dir)''',
    ''
)

# Insert the intent-driven call right after user input is processed
text = text.replace(
    'print(f"{C_SYS}  [System] User input encoded into latent space by WORKER.{C_RESET}")',
    'print(f"{C_SYS}  [System] User input encoded into latent space by WORKER.{C_RESET}")\n            sense_intent_and_ingest(memory_bank, worker_brain, workspace_dir, user_input, worker_tokenizer)'
)

with open("cli/scripts/bucket_relay_swarm_9b.py", "w") as f:
    f.write(text)
