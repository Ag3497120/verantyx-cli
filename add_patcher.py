import re

with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()

patcher_code = """
def apply_patch_to_workspace(generated_text, workspace_dir):
    \"\"\"
    Parses the [SEARCH]/[REPLACE] block from the 0.5B Coder's output
    and applies it directly to the target file in the workspace.
    \"\"\"
    import os
    import re
    
    print(f"\\n{C_CODER}[Auto-Patcher] Parsing generated diff...{C_RESET}")
    
    # Extract File path
    file_match = re.search(r"File:\s*([\\w\\./\\\\-]+)", generated_text)
    if not file_match:
        print(f"  {C_CODER}[Auto-Patcher] Error: Could not find 'File:' declaration in output.{C_RESET}")
        return False
        
    target_file = file_match.group(1).strip()
    full_path = os.path.join(workspace_dir, target_file)
    
    if not os.path.exists(full_path):
        print(f"  {C_CODER}[Auto-Patcher] Error: Target file {target_file} does not exist in workspace.{C_RESET}")
        return False
        
    # Extract SEARCH and REPLACE blocks
    search_match = re.search(r"\\[SEARCH\\]\\n(.*?)\\n\\[REPLACE\\]", generated_text, re.DOTALL)
    replace_match = re.search(r"\\[REPLACE\\]\\n(.*?)\\n\\[/REPLACE\\]", generated_text, re.DOTALL)
    
    if not search_match or not replace_match:
        print(f"  {C_CODER}[Auto-Patcher] Error: Could not find valid [SEARCH] and [REPLACE] blocks.{C_RESET}")
        return False
        
    search_content = search_match.group(1)
    replace_content = replace_match.group(1)
    
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()
            
        if search_content not in file_content:
            print(f"  {C_CODER}[Auto-Patcher] Error: SEARCH block not found in {target_file}. Semantic drift occurred!{C_RESET}")
            return False
            
        new_content = file_content.replace(search_content, replace_content, 1)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"  {C_CODER}[Auto-Patcher] Successfully patched {target_file}!{C_RESET}")
        return True
        
    except Exception as e:
        print(f"  {C_CODER}[Auto-Patcher] File operation error: {e}{C_RESET}")
        return False
"""

# Insert it before TelepathicCoderBrain
text = text.replace('class TelepathicCoderBrain:', patcher_code + '\nclass TelepathicCoderBrain:')

# Now, update `main()` in telepathic_coder_experimental.py to call it
# Wait, bucket_relay_swarm_9b.py actually calls synthesize_code. We should call apply_patch_to_workspace there!
with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)

# Now patch bucket_relay_swarm_9b.py to call apply_patch_to_workspace
with open("cli/scripts/bucket_relay_swarm_9b.py", "r") as f:
    swarm_text = f.read()
    
swarm_text = swarm_text.replace(
    'generated_code = coder.synthesize_code(scout_observation, subtask_prompt=user_input)',
    'generated_code = coder.synthesize_code(scout_observation, subtask_prompt=user_input)\n    from telepathic_coder_experimental import apply_patch_to_workspace\n    apply_patch_to_workspace(generated_code, workspace_dir)'
)

with open("cli/scripts/bucket_relay_swarm_9b.py", "w") as f:
    f.write(swarm_text)
