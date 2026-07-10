import os
import subprocess

def read_file(filepath: str) -> str:
    """Reads the contents of a file."""
    try:
        if not os.path.exists(filepath):
            return f"Error: File '{filepath}' not found."
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            return content
    except Exception as e:
        return f"Error reading file '{filepath}': {str(e)}"

def run_cmd(cmd: str) -> str:
    """Runs a shell command and returns the output. Useful for ls, grep, etc."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr
        return output if output else "[Command completed with no output]"
    except subprocess.TimeoutExpired:
        return f"Error: Command '{cmd}' timed out."
    except Exception as e:
        return f"Error running command '{cmd}': {str(e)}"

def web_search(query: str) -> str:
    """Performs a web search using DuckDuckGo Lite."""
    import urllib.request
    import urllib.parse
    import re
    try:
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            
            # Simple extraction of result snippets
            snippets = re.findall(r'<td class="result-snippet">(.+?)</td>', html, re.IGNORECASE | re.DOTALL)
            if not snippets:
                return "No clear results found for query."
                
            clean_snippets = []
            for s in snippets[:3]:
                # strip html tags
                clean = re.sub(r'<[^>]+>', '', s).strip()
                clean_snippets.append(clean)
                
            return "\n\n".join(clean_snippets)
    except Exception as e:
        return f"Error performing web search for '{query}': {str(e)}"

def visual_web_search(intent_tensor) -> str:
    """
    Pure Multimodal Search Mockup: Translates an abstract intent tensor directly into 
    a visual image representation, and performs a web search based on that image.
    Bypasses language completely.
    """
    import hashlib
    import torch
    
    if isinstance(intent_tensor, str):
        # Fallback if somehow called with string during transition
        tensor_bytes = intent_tensor.encode()
        energy = 0.0
    elif isinstance(intent_tensor, torch.Tensor):
        # Convert tensor to raw bytes for visual mapping
        tensor_bytes = intent_tensor.detach().cpu().float().numpy().tobytes()
        energy = torch.norm(intent_tensor).item()
    else:
        tensor_bytes = b"unknown_intent"
        energy = 0.0
        
    image_hash = hashlib.md5(tensor_bytes).hexdigest()[:8]
    simulated_image_url = f"https://verantyx.latent.space/visual_intent_{image_hash}.png"
    
    return (
        f"[Visual Web Search Complete]\n"
        f"1. Pure Intent Vector (Energy: {energy:.2f}) projected to Image: {simulated_image_url}\n"
        f"2. Image analyzed via latent reverse-search (Simulated).\n"
        f"3. Result: Found geometric and structural concepts matching the visual query.\n"
        f"   Identified matching architectural patterns and UI components without using words."
    )

def build_visual_scaffold(target_dir: str) -> str:
    """
    Visual Scaffold Tool: Generates a 2D/3D interactive dependency graph (D3.js).
    This serves as the silent architect's canvas to project non-verbal state.
    """
    import os
    from pathlib import Path
    import sys
    
    # ensure cli/scripts is in path
    cli_scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if cli_scripts_dir not in sys.path:
        sys.path.append(cli_scripts_dir)
        
    try:
        from visual_scaffold import generate_base_scaffold
        
        path = Path(target_dir).resolve()
        if not path.exists() or not path.is_dir():
            return f"Error: Directory '{target_dir}' does not exist."
            
        output_html = path / "dependency_graph.html"
        result_msg = generate_base_scaffold(str(path), str(output_html))
        
        return result_msg
        
    except Exception as e:
        return f"Error building visual scaffold: {str(e)}"


def generate_skill(argument: str) -> str:
    """Generates a reusable skill script. Expected argument format: name | code"""
    try:
        parts = argument.split("|", 1)
        if len(parts) != 2:
            return "Error: format must be 'skill_name | code'"
        name, code = parts[0].strip(), parts[1].strip()
        skill_dir = WORKSPACE_ROOT / ".verantyx_skills"
        skill_dir.mkdir(exist_ok=True)
        
        # simple sanitization
        safe_name = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
        skill_path = skill_dir / f"{safe_name}.py"
        
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(code)
            
        return f"Skill '{safe_name}' successfully generated at {skill_path}"
    except Exception as e:
        return f"Error generating skill: {str(e)}"

def parse_action(text: str):
    """
    Parses Commander's output for tool actions.
    Expected format: [ACTION: read_file: /path/to/file] or [ACTION: done]
    Returns (tool_name, argument) or (None, None)
    """
    import re
    # Try parsing with argument first: [ACTION: tool: argument]
    match = re.search(r"\[ACTION:\s*([^:]+):\s*([^\]]+)\]", text, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower(), match.group(2).strip()
        
    # Try parsing without argument: [ACTION: done]
    match = re.search(r"\[ACTION:\s*([^:\]]+)\]", text, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower(), ""
        
    return None, None

import json
import os
from pathlib import Path
from prompt_toolkit.shortcuts import radiolist_dialog

PERMISSION_FILE = os.path.expanduser("~/.verantyx_secure/permissions.json")
# Define the workspace root (inspired by claw-code WorkspacePathScope)
WORKSPACE_ROOT = Path(os.getcwd()).resolve()

def load_permissions():
    if os.path.exists(PERMISSION_FILE):
        try:
            with open(PERMISSION_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"always_allow": []}

def save_permissions(data):
    os.makedirs(os.path.dirname(PERMISSION_FILE), exist_ok=True)
    with open(PERMISSION_FILE, 'w') as f:
        json.dump(data, f)

def validate_path_scope(target_path_str: str) -> bool:
    """Inspired by claw-code: ensure target is within the workspace scope."""
    try:
        target_path = Path(target_path_str).resolve()
        # Check if the target path is a subpath of WORKSPACE_ROOT
        if not str(target_path).startswith(str(WORKSPACE_ROOT)):
            print(f"\n  [\033[31mScope Error\033[0m] Target '{target_path}' is strictly outside the workspace ({WORKSPACE_ROOT}). Denied.")
            return False
        return True
    except Exception:
        return False

def ask_permission(tool_name: str, argument: str) -> bool:
    # Scope Validation (claw-code harness integration)
    if tool_name in ["read_file", "run_cmd", "build_visual_scaffold"]:
        if not validate_path_scope(argument):
            return False

    perms = load_permissions()
    for allowed in perms.get("always_allow", []):
        if argument.startswith(allowed):
            return True
            
    result = radiolist_dialog(
        title=f"Security Check: {tool_name}",
        text=f"Commander requested to execute [{tool_name}] on:\n\n{argument}\n\nWorkspace: {WORKSPACE_ROOT}\n\nAllow this action?",
        values=[
            ("once", "Allow Once"),
            ("always", "Always Allow (for this path/command prefix)"),
            ("deny", "Deny")
        ]
    ).run()
    
    if result == "always":
        perms.setdefault("always_allow", []).append(argument)
        save_permissions(perms)
        return True
    elif result == "once":
        return True
    else:
        return False

def execute_action(tool_name: str, argument: str) -> str:
    print(f"\n  [\033[36mAmbient Tool\033[0m] Commander wants to execute '{tool_name}' on '{argument}'...")
    
    # discuss tool bypasses normal security dialog because it interacts directly with the user
    if tool_name == "discuss":
        return f"__DISCUSSION_REQUESTED__{argument}"

    if not ask_permission(tool_name, argument):
        print(f"  [\033[31mSecurity\033[0m] Action '{tool_name}' denied by user.")
        return f"Error: User denied permission to execute '{tool_name}' on '{argument}'."
        
    print(f"  [\033[32mSecurity\033[0m] Action allowed. Executing...")
    if tool_name == "read_file":
        return read_file(argument)
    elif tool_name == "run_cmd":
        return run_cmd(argument)
    elif tool_name == "web_search":
        return web_search(argument)
    elif tool_name == "generate_skill":
        return generate_skill(argument)
    elif tool_name == "build_visual_scaffold":
        return build_visual_scaffold(argument)
    elif tool_name == "visual_web_search":
        return visual_web_search(argument)
    else:
        return f"Error: Tool '{tool_name}' not found."
