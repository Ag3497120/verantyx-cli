import os

with open("cli/scripts/bucket_relay_swarm_9b.py", "r") as f:
    text = f.read()

ingest_func = """
def ingest_workspace(memory_bank, worker_brain, workspace_dir):
    \"\"\"
    Scans the workspace for code files and injects them into the Eternal Memory.
    Acts as the Project Omniscience / KV Cache pre-fill phase.
    \"\"\"
    print(f"\\n{C_SYS}=== Project Omniscience (Eternal Memory Ingestion) ==={C_RESET}")
    print(f"{C_SYS}  [System] Scanning {workspace_dir} for project files...{C_RESET}")
    
    # Quick check for already indexed files
    indexed_files = set()
    for item in memory_bank.zone_b_index:
        label = item.get("label", "")
        if label.startswith("File: "):
            indexed_files.add(label.replace("File: ", "").strip())
            
    import glob
    search_pattern = os.path.join(workspace_dir, "**", "*")
    
    count = 0
    from transformers import AutoTokenizer
    # We will need the tokenizer to encode.
    try:
        worker_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B")
    except:
        return
        
    for file_path in glob.glob(search_pattern, recursive=True):
        if not os.path.isfile(file_path):
            continue
        rel_path = os.path.relpath(file_path, workspace_dir)
        
        # Skip hidden files, __pycache__, and binaries/logs
        if any(part.startswith('.') for part in rel_path.split(os.sep)):
            continue
        if "__pycache__" in rel_path or "node_modules" in rel_path:
            continue
        if not (rel_path.endswith('.py') or rel_path.endswith('.ts') or rel_path.endswith('.md')):
            continue
            
        if rel_path in indexed_files:
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except:
            continue
            
        if not content.strip():
            continue
            
        # Chunking if file is too big (very basic chunking for now)
        if len(content) > 4000:
            content = content[:4000]
            
        # Encode and add to memory
        formatted_text = f"File: {rel_path}\\nContent:\\n{content}"
        vector = worker_brain.encode_text(formatted_text, worker_tokenizer).to(worker_brain.device)
        memory_bank.add_memory(vector, label=f"File: {rel_path}", defer_save=True)
        count += 1
        
    if count > 0:
        memory_bank._save_to_ssd()
        print(f"{C_SYS}  [System] Successfully ingested {count} new files into Eternal Memory.{C_RESET}")
    else:
        print(f"{C_SYS}  [System] Project memory is fully up to date.{C_RESET}")

"""

# Insert before if __name__ == "__main__":
text = text.replace('if __name__ == "__main__":', ingest_func + '\nif __name__ == "__main__":')

# Also, update the main block to call this after worker_brain is loaded
# The worker_brain is loaded around line 1087 (in the original text)
# Wait, worker_brain is loaded ONLY if user_input is given!
# Let's fix that. worker_brain should be loaded unconditionally.

replacement_main = """
    # Worker Brain (Qwen 0.5B)
    workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    worker_jgen = "/Users/motonishikoudai/verantyx-cli/qwen_9b_full.jgen"
    if not os.path.exists(worker_jgen):
        worker_jgen = "/Users/motonishikoudai/verantyx-cli/qwen_9b_full.jgen"
    print(f"{C_SYS}  [System] Loading Qwen tokenizer for Worker Encoding...{C_RESET}")
    from transformers import AutoTokenizer
    worker_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B")
    worker_brain = JCrossBrain(worker_jgen, device)
    
    # -----------------------------------------------------
    # ETERNAL MEMORY INGESTION (PROJECT OMNISCIENCE)
    # -----------------------------------------------------
    ingest_workspace(memory_bank, worker_brain, workspace_dir)
"""

text = text.replace(
    '    if memory_bank.consensus_vector is not None:',
    replacement_main + '\n    if memory_bank.consensus_vector is not None:'
)

# Also we must remove the duplicate worker_brain loading from the `if user_input:` block
text = text.replace(
'''            from transformers import AutoTokenizer
            print(f"{C_SYS}  [System] Loading Qwen tokenizer for Worker Encoding...{C_RESET}")
            worker_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B")
            
            workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            worker_jgen = "/Users/motonishikoudai/verantyx-cli/qwen_9b_full.jgen"
            if not os.path.exists(worker_jgen):
                worker_jgen = "/Users/motonishikoudai/verantyx-cli/qwen_9b_full.jgen"
            worker_brain = JCrossBrain(worker_jgen, device)''',
            '            # Worker brain is already loaded above.'
)

with open("cli/scripts/bucket_relay_swarm_9b.py", "w") as f:
    f.write(text)
