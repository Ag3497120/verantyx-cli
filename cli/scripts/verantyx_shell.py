import os
import sys
import time
import random
import torch
import pyfiglet
import numpy as np
import asyncio
import websockets
import json
import threading
from PIL import Image, ImageDraw, ImageFont
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from rich.console import Console

from bucket_relay_swarm import TelepathicMemoryBank, JCrossBrain, purge_memory
from bucket_relay_swarm import C_WORKER, C_CMDR, C_SCOUT, C_SYS, C_RESET
from matrix_ui import MatrixUIDecoder
from chrono_memory import ChronoRegistry
from two_phase_commit import execute_mediator_flow

# --- WebSocket Server Setup ---
connected_clients = set()
ws_loop = None

async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)

def trigger_visual_search_async(action_vector, user_input):
    """
    Asynchronously triggers the visual web search tool, generating a PNG image
    and sending it to the UI Hub without blocking the main swarm debate.
    """
    import hashlib
    hash_val = hashlib.md5(action_vector.detach().cpu().float().numpy().tobytes()).hexdigest()[:6]
    
    # Create image
    img = Image.new('RGB', (600, 300), color='#0b0c10')
    draw = ImageDraw.Draw(img)
    
    prompt_text = f"SEARCH REQUEST (Asynchronous Crawler)\nUser Input: {user_input}\nIntent Hash: {hash_val}\n\nPlease search for the latest information\nregarding the user input and provide\na concise technical summary."
    draw.text((20, 20), prompt_text, fill='#66fcf1')
    draw.text((20, 250), "Verantyx AI - Visual Intent", fill='#45a29e')
    
    # Save as PNG
    intents_dir = "/Users/motonishikoudai/verantyx-cli/cortex/verantyx-ui-hub/public/intents"
    os.makedirs(intents_dir, exist_ok=True)
    file_name = f"intent_{hash_val}.png"
    file_path = os.path.join(intents_dir, file_name)
    img.save(file_path)
        
    intent_msg = {
        "type": "image_intent",
        "url": f"/intents/{file_name}"
    }
    
    ws_message = {
        "type": "action",
        "tool": "visual_web_search",
        "confidence": 0.99, # High confidence for asynchronous trigger
        "argument": "vector_payload_omitted"
    }
    
    for client in list(connected_clients):
        try:
            if ws_loop and ws_loop.is_running():
                asyncio.run_coroutine_threadsafe(client.send(json.dumps(ws_message)), ws_loop)
                asyncio.run_coroutine_threadsafe(client.send(json.dumps(intent_msg)), ws_loop)
        except Exception as e:
            pass

async def start_ws_server():
    async with websockets.serve(ws_handler, "localhost", 8765):
        await asyncio.Future()  # run forever

def run_ws_thread():
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)
    ws_loop.run_until_complete(start_ws_server())

ws_thread = threading.Thread(target=run_ws_thread, daemon=True)
ws_thread.start()
print("  [\033[36mWebSocket\033[0m] Brain Neural Link active on ws://localhost:8765")

# Add current directory to path so we can import ambient_tools
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from ambient_tools import parse_action, execute_action

# --- UI Theme Colors ---
ASCII_COLORS = ["\033[36m", "\033[35m", "\033[32m", "\033[33m", "\033[31m", "\033[34m"]

console = Console()

class ActionSpace:
    """
    Pure Multimodal Action Space.
    Bypasses language completely by mapping JCross intent vectors
    directly to tool actions using Cosine Similarity against spatial anchor vectors.
    """
    def __init__(self, hidden_dim=4096, device="cpu"):
        self.hidden_dim = hidden_dim
        self.device = device
        self.anchors = {}
        
        # Define orthogonal random anchors for core tools.
        # In a fully trained system, these would be learned latent clusters.
        self._register_anchor("visual_web_search", seed=10)
        self._register_anchor("build_visual_scaffold", seed=20)
        self._register_anchor("discuss", seed=30)
        self._register_anchor("done", seed=40)
        self._register_anchor("propose_edit_intent", seed=50)
        
        print(f"  [\033[34mActionSpace\033[0m] Initialized {len(self.anchors)} purely spatial tool anchors. Linguistic Decoder is completely offline.")

    def _register_anchor(self, tool_name, seed):
        torch.manual_seed(seed)
        v = torch.randn(1, self.hidden_dim, dtype=torch.float16, device=self.device)
        self.anchors[tool_name] = v / torch.norm(v)

    def match_action(self, intent_vector: torch.Tensor):
        iv = intent_vector.detach().to(torch.float16)
        
        # Dimension alignment (e.g. 3840 -> 4096)
        current_dim = iv.shape[-1]
        if current_dim < self.hidden_dim:
            pad_size = self.hidden_dim - current_dim
            iv = torch.nn.functional.pad(iv, (0, pad_size), "constant", 0)
        elif current_dim > self.hidden_dim:
            iv = iv[..., :self.hidden_dim]
            
        iv_norm = iv / (torch.norm(iv) + 1e-6)
        
        best_tool = "visual_web_search" # default
        best_score = -float('inf')
        
        for tool_name, anchor in self.anchors.items():
            score = torch.nn.functional.cosine_similarity(iv_norm, anchor).item()
            if score > best_score:
                best_score = score
                best_tool = tool_name
                
        return best_tool, best_score

    def encode_dummy(self, seed_val):
        """Generates a reproducible dummy vector for initialization/feedback without using text."""
        h = hash(str(seed_val)) % 10000
        torch.manual_seed(h)
        v = torch.randn(1, self.hidden_dim, dtype=torch.float16, device=self.device)
        return v

def print_ascii_art():
    ascii_art = pyfiglet.figlet_format("VERANTYX", font="slant")
    color = random.choice(ASCII_COLORS)
    os.system('cls' if os.name == 'nt' else 'clear')
    sys.stdout.write(f"{color}{ascii_art}{C_RESET}\n")
    sys.stdout.write(f"  [System] Autonomous Homeostasis Core (The Silent Architect) initialized.\n")
    sys.stdout.write(f"  [System] Input parameters/vectors. Awaiting architectural triggers...\n")
    sys.stdout.write("-" * 60 + "\n\n")
    sys.stdout.flush()

def calculate_similarity(intent_vector, memory_bank):
    if memory_bank.memory_tensor is None or memory_bank.memory_tensor.size(0) == 0:
        return 0.0
    with torch.no_grad():
        intent_cpu = intent_vector.detach().cpu().to(torch.float32)
        memory_cpu = memory_bank.memory_tensor.detach().cpu().to(torch.float32)
        
        # Dimension alignment
        if intent_cpu.shape[-1] != memory_cpu.shape[-1]:
            diff = intent_cpu.shape[-1] - memory_cpu.shape[-1]
            if diff > 0:
                memory_cpu = torch.nn.functional.pad(memory_cpu, (0, diff))
            else:
                intent_cpu = torch.nn.functional.pad(intent_cpu, (0, -diff))
                
        sims = torch.nn.functional.cosine_similarity(intent_cpu, memory_cpu)
        return torch.max(sims).item()

def memorize_workspace(directory, memory_bank, action_space, chrono_registry):
    import subprocess
    print(f"\n{C_SYS}  [Vectorization] Scanning workspace: {directory}...{C_RESET}")
    
    # Get current git commit hash for the directory
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=directory, capture_output=True, text=True, check=True)
        commit_hash = result.stdout.strip()
    except Exception:
        commit_hash = "no_git"
        
    total_chunks = 0
    for root, _, files in os.walk(directory):
        if "node_modules" in root or ".git" in root or "dist" in root or ".verantyx_chrono" in root:
            continue
        for file in files:
            if file.endswith((".py", ".ts", ".tsx", ".js", ".html", ".css", ".md")):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    # Chunk every 50 lines for broad conceptual vectors
                    for i in range(0, len(lines), 50):
                        chunk = "".join(lines[i:i+50]).strip()
                        if len(chunk) > 10:
                            # Use action_space dummy encoder to convert code chunk to vector
                            chunk_vector = action_space.encode_dummy(f"Code Context: {filepath} L{i}-{i+50}\n{chunk}")
                            idx = memory_bank.add_memory(chunk_vector, label=f"File: {os.path.basename(filepath)}")
                            chrono_registry.add_entry(
                                vector_index=idx,
                                filepath=filepath,
                                start_line=i+1,
                                end_line=i+50,
                                git_commit_hash=commit_hash,
                                parent_index=-1
                            )
                            total_chunks += 1
                            if total_chunks % 10 == 0:
                                print(f"  [Vectorization] Indexed {total_chunks} code chunks...")
                except Exception as e:
                    pass
    
    print(f"{C_SYS}  [Vectorization] Complete! Added {total_chunks} spatial vectors to Eternal Memory and Registry.{C_RESET}\n")

def launch_hand_terminal(workspace_dir):
    """
    Launches a new macOS Terminal window to tail the Hand CLI log file.
    """
    import subprocess
    log_dir = os.path.join(workspace_dir, ".verantyx_chrono")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "hand.log")
    
    # Touch the file to ensure it exists
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("[System] The Hand Logging Terminal Initialized\n")
            
    apple_script = f'''
    tell application "Terminal"
        do script "clear && echo '\\033[36m=== Verantyx The Hand CLI Monitor ===\\033[0m' && tail -f '{log_file}'"
        activate
    end tell
    '''
    try:
        subprocess.run(['osascript', '-e', apple_script], check=True)
        print(f"  [\033[36mSystem\033[0m] Hand CLI Monitoring Terminal launched.")
    except Exception as e:
        print(f"  [\033[33mWarning\033[0m] Failed to launch Hand Terminal: {e}")

async def main():
    print_ascii_art()
    
    workspace_dir = os.getcwd()
    launch_hand_terminal(workspace_dir)
    
    print("\nSelect Autonomous Swarm Mode (Discussion Limits):")
    print("  [1] Low Mode (Max 5 discussion steps, fast execution)")
    print("  [2] Medium Mode (Max 15 discussion steps, balanced)")
    print("  [3] High Mode (Max 30 discussion steps, deep planning)")
    print("  [4] Auto Mode (Dynamic limit based on task complexity)")
    try:
        mode_choice = input("Select mode [1/2/3/4]> ").strip()
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)
        
    if mode_choice == '1': mode_name, default_depth, default_thresh, max_steps = "Low", 10, 0.35, 5
    elif mode_choice == '2': mode_name, default_depth, default_thresh, max_steps = "Medium", 50, 0.45, 15
    elif mode_choice == '3': mode_name, default_depth, default_thresh, max_steps = "High", 100, 0.50, 30
    else: mode_name, default_depth, default_thresh, max_steps = "Auto", None, None, 15
    
    print(f"  [\033[36mSystem\033[0m] Mode set to: \033[1m{mode_name}\033[0m (Max Steps: {max_steps})")
    
    bindings = KeyBindings()
    
    @bindings.add('escape', 'enter')
    def _(event):
        event.current_buffer.validate_and_handle()
        
    style = Style.from_dict({'prompt': 'ansicyan bold'})
    session = PromptSession(message='Swarm> ', multiline=True, key_bindings=bindings, style=style)
    
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    # CLI scripts directory relative path logic to find .jgen files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(script_dir))
    worker_jgen = os.path.join(root_dir, "cli/gemma_12b_generative.jgen")
    commander_jgen = os.path.join(root_dir, "cli/commander_12b_rank1024.jgen")
    scout_jgen = commander_jgen

    print(f"{C_SYS}  [System] Waking up Eternal Database...{C_RESET}")
    memory_bank = TelepathicMemoryBank()
    
    print(f"{C_SYS}  [System] Waking up Chrono Registry...{C_RESET}")
    chrono_registry = ChronoRegistry(workspace_dir=workspace_dir)
    
    print(f"{C_SYS}  [System] Initializing Tool Anchors...{C_RESET}")
    action_space = ActionSpace(hidden_dim=4096, device=device)
    
    intent_vector = action_space.encode_dummy("Initial Boot Sequence")
    last_ctrl_c_time = 0
    ctrl_c_count = 0
    is_first_query = True

    while True:
        try:
            user_input = await session.prompt_async()
            last_ctrl_c_time = 0
            ctrl_c_count = 0
            if not user_input.strip(): continue
            if user_input.strip() in ['exit', 'quit']: break
            
            if user_input.strip() == "/memorize":
                memorize_workspace(workspace_dir, memory_bank, action_space, chrono_registry)
                continue
                
            # --- Auto-Memorize on First Query ---
            if is_first_query:
                is_first_query = False
                print(f"  [\033[36mSystem\033[0m] Initializing Auto-Memorize for workspace: {workspace_dir}")
                try:
                    import subprocess
                    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=workspace_dir, capture_output=True, text=True, check=True)
                    current_hash = result.stdout.strip()
                    
                    # Check if hash already exists in registry
                    hash_exists = False
                    for entry in chrono_registry.entries.values():
                        if entry.get("git_commit_hash") == current_hash:
                            hash_exists = True
                            break
                            
                    if hash_exists:
                        print(f"  [\033[32mSystem\033[0m] Vector translation for current state ({current_hash[:8]}) already completed. Skipping.")
                    else:
                        print(f"  [\033[33mSystem\033[0m] Current state ({current_hash[:8]}) is new. Proceeding with Vector Translation...")
                        memorize_workspace(workspace_dir, memory_bank, action_space, chrono_registry)
                except Exception:
                    print(f"  [\033[33mSystem\033[0m] Not a git repository or git error. Proceeding with forced Vector Translation...")
                    memorize_workspace(workspace_dir, memory_bank, action_space, chrono_registry)
            
            print(f"\n[\033[36mSYSTEM\033[0m] Initiating Verantyx Flow...\n")
            
            intent_vector = action_space.encode_dummy(f"User Request: {user_input}")
            base_thought = intent_vector.clone()
            current_thought = intent_vector.clone()
            
            print(f"  [\033[33mCommander\033[0m] Comparing intent with Eternal Memory for Deep Insights...")
            current_thought = memory_bank.retrieve_memory(intent_vector)
            
            if mode_name == "Dynamic":
                max_sim = calculate_similarity(intent_vector, memory_bank)
                if max_sim < 0.85:
                    max_depth, threshold = 100, 0.50
                    print(f"  [\033[35mDynamic Mode\033[0m] Complex task detected (Sim: {max_sim:.2f}). Activating Deep Thinking...")
                else:
                    max_depth, threshold = 10, 0.35
                    print(f"  [\033[35mDynamic Mode\033[0m] Familiar task detected (Sim: {max_sim:.2f}). Activating Quick Response...")
            else:
                max_depth, threshold = default_depth, default_thresh
                
            step_count = 0
            matrix_ui = MatrixUIDecoder()
            
            while step_count < max_steps:
                step_count += 1
                if max_steps > 1:
                    print(f"\n  [\033[33mSwarm Loop\033[0m] Step {step_count}/{max_steps} started...")
                
                memory_bank.ambient_leak(intent_vector, label=f"Commander Intent (Step {step_count})")
                
                if memory_bank.memory_tensor is not None:
                    telepathy_vectors = memory_bank.memory_tensor[-5:].unsqueeze(0)
                else:
                    telepathy_vectors = action_space.encode_dummy("Initial state").unsqueeze(0)
                
                print(f"  [\033[35mScout 1\033[0m] Reconnaissance & Analysis (Vector Level)...")
                try:
                    scout_brain = JCrossBrain(scout_jgen, device)
                    recon_vector = scout_brain.forward_latent(current_thought, role_name="Scout 1", color_code="\033[35m")
                    features = matrix_ui.record_step("Scout 1", recon_vector, current_thought)
                    print(f"  {matrix_ui.render_terminal_progress('Scout 1', features, '\033[35m')}")
                    del scout_brain
                    purge_memory()
                except Exception as e:
                    recon_vector = current_thought

                print(f"  [\033[36mWorkers\033[0m] 3-Node Sequential Debate (Forming Consensus)...")
                debate_vector = recon_vector.clone()
                try:
                    worker_brain = JCrossBrain(worker_jgen, device)
                    for w_idx in range(1, 4):
                        prev_debate = debate_vector.clone()
                        
                        role_name = f"Worker {w_idx}"
                        if w_idx == 2:
                            role_name = "Worker 2 (Search Crawler)"
                            
                        debate_vector = worker_brain.forward_latent(debate_vector, role_name=role_name, color_code="\033[36m")
                        features = matrix_ui.record_step(role_name, debate_vector, prev_debate)
                        print(f"  {matrix_ui.render_terminal_progress(role_name, features, '\033[36m')}")
                        
                        if w_idx == 2:
                            if features["variance"] > 0.05 or features["energy"] > 60.0:
                                print(f"  [\033[36mSearch Crawler\033[0m] \033[32mIntrigued by the problem. Throwing async search intent to User!\033[0m")
                                threading.Thread(target=trigger_visual_search_async, args=(debate_vector.clone(), user_input)).start()
                                
                    del worker_brain
                    purge_memory()
                except Exception as e:
                    pass
                worker_consensus = debate_vector.clone()

                print(f"  [\033[33mCommander\033[0m] Intervention & Strategy Alignment...")
                try:
                    cmdr_brain = JCrossBrain(commander_jgen, device)
                    cmdr_intent = cmdr_brain.forward_latent(worker_consensus, role_name="Commander", color_code="\033[33m")
                    features = matrix_ui.record_step("Commander", cmdr_intent, worker_consensus)
                    print(f"  {matrix_ui.render_terminal_progress('Commander', features, '\033[33m')}")
                    del cmdr_brain
                    purge_memory()
                except Exception as e:
                    cmdr_intent = worker_consensus
                
                print(f"  [\033[35mScout 2\033[0m] Operational Execution Decision...")
                try:
                    scout_brain2 = JCrossBrain(scout_jgen, device)
                    action_vector = scout_brain2.forward_latent(cmdr_intent, role_name="Scout 2", color_code="\033[35m")
                    features = matrix_ui.record_step("Scout 2", action_vector, cmdr_intent)
                    print(f"  {matrix_ui.render_terminal_progress('Scout 2', features, '\033[35m')}")
                    del scout_brain2
                    purge_memory()
                except Exception as e:
                    action_vector = cmdr_intent
                
                current_thought = action_vector.clone()

                print(f"  [\033[34mActionSpace\033[0m] Matching Swarm Intent against tool anchors...")
                
                tool_name, confidence = action_space.match_action(action_vector)
                
                print(f"\n" + "="*60)
                print(f"[\033[35mVerantyx Spatial Trigger\033[0m] Triggered Tool: {tool_name} (Confidence: {confidence:.3f})")
                print("="*60 + "\n")
                
                if tool_name == "done":
                    print("  [\033[32mSwarm\033[0m] Swarm declared task complete.")
                    break
                
                argument = ""
                if tool_name == "visual_web_search":
                    argument = action_vector
                elif tool_name == "build_visual_scaffold":
                    argument = "/Users/motonishikoudai/verantyx-cli/cortex/verantyx-browser"
                elif tool_name == "discuss":
                    argument = "Swarm requires human feedback to adjust its topology."
                elif tool_name == "propose_edit_intent":
                    argument = os.path.join(workspace_dir, "index.html")
                    
                ws_message = {
                    "type": "action",
                    "tool": tool_name,
                    "confidence": float(confidence),
                    "argument": "vector_payload_omitted" if (tool_name == "visual_web_search" or tool_name == "propose_edit_intent") else str(argument)
                }
                
                if tool_name == "visual_web_search":
                    import hashlib
                    hash_val = hashlib.md5(action_vector.detach().cpu().float().numpy().tobytes()).hexdigest()[:6]
                    
                    img = Image.new('RGB', (600, 300), color='#0b0c10')
                    draw = ImageDraw.Draw(img)
                    
                    prompt_text = f"SEARCH REQUEST\nUser Input: {user_input}\nIntent Hash: {hash_val}\n\nPlease search for the latest information\nregarding the user input and provide\na concise technical summary."
                    draw.text((20, 20), prompt_text, fill='#66fcf1')
                    draw.text((20, 250), "Verantyx AI - Visual Intent", fill='#45a29e')
                    
                    intents_dir = "/Users/motonishikoudai/verantyx-cli/cortex/verantyx-ui-hub/public/intents"
                    os.makedirs(intents_dir, exist_ok=True)
                    file_name = f"intent_{hash_val}.png"
                    file_path = os.path.join(intents_dir, file_name)
                    img.save(file_path)
                        
                    intent_msg = {
                        "type": "image_intent",
                        "url": f"/intents/{file_name}"
                    }
                    for client in list(connected_clients):
                        try:
                            if ws_loop and ws_loop.is_running():
                                asyncio.run_coroutine_threadsafe(client.send(json.dumps(ws_message)), ws_loop)
                                asyncio.run_coroutine_threadsafe(client.send(json.dumps(intent_msg)), ws_loop)
                        except Exception as e:
                            pass
                else:
                    for client in list(connected_clients):
                        try:
                            if ws_loop and ws_loop.is_running():
                                asyncio.run_coroutine_threadsafe(client.send(json.dumps(ws_message)), ws_loop)
                        except Exception as e:
                            pass
                            
                if tool_name == "propose_edit_intent":
                    tool_result = execute_mediator_flow(action_vector, argument, chrono_registry, action_space, memory_bank)
                    if tool_result:
                        tool_result = "Mediator successfully applied code changes."
                    else:
                        tool_result = "Mediator failed to apply code changes or Swarm vetoed it."
                else:
                    tool_result = execute_action(tool_name, argument)
                
                if isinstance(tool_result, str) and tool_result.startswith("__DISCUSSION_REQUESTED__"):
                    question = tool_result.replace("__DISCUSSION_REQUESTED__", "")
                    print(f"\n  [\033[35mDiscussion\033[0m] {question}")
                    try:
                        user_reply = input("  [Your Reply]> ").strip()
                        tool_result = f"User responded: {user_reply}"
                    except (KeyboardInterrupt, EOFError):
                        tool_result = "User aborted the discussion."
                        
                print(f"  [\033[32mTool Result\033[0m] {str(tool_result)[:300]}...\n")
                
                tool_vector = action_space.encode_dummy(f"Tool Feedback: {tool_name}")
                memory_bank.ambient_leak(tool_vector, label=f"Tool Feedback ({tool_name})")
            
        except KeyboardInterrupt:
            current_time = time.time()
            if current_time - last_ctrl_c_time < 2.0:
                ctrl_c_count += 1
            else:
                ctrl_c_count = 1
                
            last_ctrl_c_time = current_time
            
            if ctrl_c_count == 1:
                # Save session state on first press
                state_file = os.path.join(workspace_dir, ".verantyx_chrono", "session_state.json")
                os.makedirs(os.path.dirname(state_file), exist_ok=True)
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": current_time,
                        "vector_count": memory_bank.memory_tensor.shape[0] if memory_bank.memory_tensor is not None else 0,
                        "status": "Vectorization and memory states safely anchored."
                    }, f, indent=2)
                print(f"\n  [\033[32mSystem\033[0m] Memory translation and vector states safely anchored.")
                print(f"  [\033[33mInfo\033[0m] Press \033[1mCtrl+C\033[0m rapidly 3 more times to terminate process.")
                continue
            elif ctrl_c_count >= 4:
                print("\nExiting Verantyx Shell. Memory safely preserved on SSD.")
                break
            else:
                remaining = 4 - ctrl_c_count
                print(f"\n  [\033[33mInfo\033[0m] Press \033[1mCtrl+C\033[0m rapidly {remaining} more times to terminate.")
                continue
                
        except EOFError:
            break
        except Exception as e:
            print(f"[\033[31mERROR\033[0m] {e}")

if __name__ == "__main__":
    asyncio.run(main())
