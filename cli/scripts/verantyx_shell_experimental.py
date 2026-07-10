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

# Prevent MPS Allocator from artificially restricting VRAM usage and causing OOM
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

from PIL import Image, ImageDraw, ImageFont
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from rich.console import Console

from bucket_relay_swarm_experimental import TelepathicMemoryBank, JCrossBrain, purge_memory
from bucket_relay_swarm_experimental import C_WORKER, C_CMDR, C_SCOUT, C_SYS, C_RESET
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
    def __init__(self, hidden_dim=3840, device="cpu"):
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
    if len(memory_bank.zone_b_index) == 0:
        return 0.0
    
    memory_bank._lazy_load_zone_a()
    if memory_bank.zone_a_cache is None or memory_bank.zone_a_cache.size(0) == 0:
        return 0.0
        
    with torch.no_grad():
        intent_cpu = intent_vector.detach().cpu().to(torch.float32)
        memory_cpu = memory_bank.zone_a_cache.detach().cpu().to(torch.float32)
        
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
        
    ignore_dirs = {
        "node_modules", ".git", "dist", ".verantyx_chrono", "venv", ".venv", "env", "__pycache__", "build", "target"
    }
    
    # --- Pre-scan to calculate total progress ---
    print(f"{C_SYS}  [Vectorization] Pre-scanning files to calculate progress...{C_RESET}")
    filepaths_to_process = []
    total_chunks_expected = 0
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for file in files:
            if file.endswith((".py", ".ts", ".tsx", ".js", ".html", ".css", ".md")):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    chunks = len(lines) // 50 + (1 if len(lines) % 50 != 0 else 0)
                    if chunks > 0:
                        total_chunks_expected += chunks
                        filepaths_to_process.append((filepath, lines))
                except Exception:
                    pass
                    
    print(f"{C_SYS}  [Vectorization] Found {len(filepaths_to_process)} files, {total_chunks_expected} chunks to process.{C_RESET}")
    
    if total_chunks_expected == 0:
        print(f"{C_SYS}  [Vectorization] No valid code files found.{C_RESET}\n")
        return
        
    total_chunks = 0
    
    # --- Actual Encoding Loop ---
    for filepath, lines in filepaths_to_process:
        try:
            for i in range(0, len(lines), 50):
                chunk = "".join(lines[i:i+50]).strip()
                if len(chunk) > 10:
                    chunk_vector = action_space.encode_dummy(f"Code Context: {filepath} L{i}-{i+50}\n{chunk}")
                    idx = memory_bank.add_memory(chunk_vector, label=f"File: {os.path.basename(filepath)}", defer_save=True)
                    chrono_registry.add_entry(
                        vector_index=idx,
                        filepath=filepath,
                        start_line=i+1,
                        end_line=i+50,
                        git_commit_hash=commit_hash,
                        parent_index=-1,
                        defer_save=True
                    )
                    total_chunks += 1
                    
                    if total_chunks % 500 == 0 or total_chunks == total_chunks_expected:
                        percent = (total_chunks / total_chunks_expected) * 100
                        print(f"  [Vectorization] Progress: {percent:.1f}% ({total_chunks}/{total_chunks_expected} chunks indexed)")
        except Exception:
            pass
    
    # Batch save at the very end
    print(f"{C_SYS}  [Vectorization] Batch saving memory tensors to SSD...{C_RESET}")
    if total_chunks > 0:
        memory_bank._save_to_ssd()
        chrono_registry.save()
    
    print(f"{C_SYS}  [Vectorization] Complete! Added {total_chunks} spatial vectors to Eternal Memory and Registry.{C_RESET}\n")

async def main():
    print_ascii_art()
    
    workspace_dir = os.getcwd()
    
    print("\nSelect Autonomous Swarm Mode (Discussion Limits):")
    print("  [1] Low Mode (Max 1 discussion steps, fast execution)")
    print("  [2] Medium Mode (Max 3 discussion steps, balanced)")
    print("  [3] High Mode (Max 5 discussion steps, deep planning)")
    print("  [4] Auto Mode (Dynamic limit based on task complexity)")
    print("  [5] Ultra Thinking Mode (100-10000 steps, manually adjustable)")
    try:
        mode_choice = input("Select mode [1/2/3/4/5]> ").strip()
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)
        
    if mode_choice == '1': mode_name, default_depth, default_thresh, max_steps, search_quota = "Low", 10, 0.35, 1, 2
    elif mode_choice == '2': mode_name, default_depth, default_thresh, max_steps, search_quota = "Medium", 50, 0.45, 3, 5
    elif mode_choice == '3': mode_name, default_depth, default_thresh, max_steps, search_quota = "High", 100, 0.50, 5, 10
    elif mode_choice == '5':
        mode_name = "Ultra Thinking"
        default_depth, default_thresh, search_quota = None, None, 20
        while True:
            try:
                max_steps_input = input("Enter max steps (100-10000)> ").strip()
                max_steps = int(max_steps_input)
                if 100 <= max_steps <= 10000:
                    break
                else:
                    print("  [\033[31mError\033[0m] Value must be between 100 and 10000.")
            except ValueError:
                print("  [\033[31mError\033[0m] Please enter a valid integer.")
    else: mode_name, default_depth, default_thresh, max_steps, search_quota = "Auto", None, None, 100, 5
    
    print(f"  [\033[36mSystem\033[0m] Mode set to: \033[1m{mode_name}\033[0m (Max Steps: {max_steps})")
    
    bindings = KeyBindings()
    
    @bindings.add('escape', 'enter')
    def _(event):
        event.current_buffer.validate_and_handle()
        
    @bindings.add('c-c')
    def _(event):
        event.app.exit(exception=KeyboardInterrupt)
        
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
    action_space = ActionSpace(hidden_dim=3840, device=device)
    
    print(f"{C_SYS}  [System] Initializing Telepathic Coder (Lossless Engine)...{C_RESET}")
    from telepathic_coder_experimental import TelepathicCoder
    global_coder = TelepathicCoder(
        workspace_dir, 
        cluster_mode=args.cluster_mode, 
        worker_ip=args.worker_ip
    )
    
    rpc = None
    if args.cluster_mode == 'master':
        print(f"{C_SYS}  [System] Initializing Thunderbolt RPC Client...{C_RESET}")
        from thunderbolt_rpc import TensorTransferEngine
        rpc = TensorTransferEngine(role='master', peer_ip=args.worker_ip, port=5555)
        rpc.start()
        
    intent_vector = global_coder.text_to_intent("Initial Boot Sequence")
    last_ctrl_c_time = 0
    ctrl_c_count = 0
    is_first_query = True
    
    # Fluid Swarm State variables preserved across turns
    active_ambient_vector = None
    context_prompt = ""
    cloud_assessment = "中"  # Default assumption

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
            
            # --- Cloud Complexity Assessment Flow ---
            if active_ambient_vector is None:
                print(f"\n  [\033[36mCloud Planning\033[0m] Does this project require a complexity assessment by a Cloud AI? (y/N)")
                assessment_choice = input("  Choice> ").strip().lower()
                if assessment_choice in ['y', 'yes']:
                    assessment_prompt = (
                        "以下のプロジェクトの規模を『大』『中』『小』のいずれか1文字で評価してください。\n"
                        "理由や他の文字は一切出力しないでください。\n"
                        "※規模の基準:\n"
                        " - 大: 大規模システム（数百〜数千ファイル以上、複雑なアーキテクチャ、クラウド連携などを含む）\n"
                        " - 中: 中規模アプリ（数十〜数百ファイル、標準的なMVC/MVVMアーキテクチャ、単一のアプリなど）\n"
                        " - 小: 小規模スクリプト・機能追加（数個〜十数個のファイル、単一機能のテストなど）\n\n"
                        f"プロジェクト: {user_input}"
                    )
                    import subprocess
                    try:
                        subprocess.run(['pbcopy'], input=assessment_prompt.encode('utf-8'), check=True)
                        print("  [\033[32mSystem\033[0m] Prompt copied to clipboard! Please paste it into your Cloud AI (Gemini/ChatGPT).")
                    except Exception as e:
                        print(f"  [\033[31mError\033[0m] Failed to copy to clipboard: {e}")
                        print("  Please copy the following manually:")
                        print(f"\033[33m{assessment_prompt}\033[0m")
                        
                    cloud_assessment = input("  [\033[36mCloud Planning\033[0m] Please paste the assessment result (大, 中, or 小): ").strip()
                    if cloud_assessment not in ["大", "中", "小"]:
                        print(f"  [\033[33mWarning\033[0m] Invalid input. Defaulting to '中'.")
                        cloud_assessment = "中"
                else:
                    print(f"  [\033[33mSystem\033[0m] Skipping cloud assessment. Defaulting to '中'.")

            print(f"\n[\033[36mSYSTEM\033[0m] Initiating Verantyx Fluid Swarm Flow...\n")
            
            # 1. ユーザー入力をテレパシー空間（Ambient Vector）へ注入
            swarm_directive = "[SWARM ARCHITECT DIRECTIVE] Think as a multi-agent system architect. Deeply design the directory structure, file boundaries, and component logic. Plan to split code into multiple files."
            new_intent = global_coder.text_to_intent(f"User Request: {user_input}\n{swarm_directive}")
            
            is_user_approved = False
            if active_ambient_vector is None:
                # Initial Task
                active_ambient_vector = new_intent
                context_prompt = user_input
            else:
                # Continued Task (Human-in-the-Loop Feedback)
                ui_lower = user_input.strip().lower()
                if ui_lower in ["yes", "y", "ok", "proceed", "承認"]:
                    print(f"  [\033[35mLatent Resonance\033[0m] User approved. Amplifying vector resolution to break semantic repulsion barrier...")
                    # Artificial Latent Resonance: Boost the norm to breakthrough the repulsion filter
                    active_ambient_vector = active_ambient_vector * 1.0 # Maintain stable norm (removed * 10.0)
                    is_user_approved = True
                else:
                    print(f"  [\033[35mLatent Resonance\033[0m] User provided feedback. Blending new context into thought vector...")
                    # Blend feedback and boost slightly
                    active_ambient_vector = (active_ambient_vector + new_intent) * 1.0 # Maintain stable norm (removed * 2.0)
                    context_prompt += f"\nFeedback: {user_input}"
            
            # Retrieve from Eternal Memory (RAG in Latent Space)
            active_ambient_vector = memory_bank.retrieve_memory(active_ambient_vector, k=10, blend_ratio=0.5)
            
            ambient_vector = active_ambient_vector.clone()
            memory_bank.diffuse_thought(ambient_vector, intensity=1.0, flag_label="User Intent/Feedback", agent_id=0)
            
            # The Telepathic Field Loop (Fluid Swarm)
            flow_active = True
            current_stage = "planning" # Used for structural debate tracking
            matrix_ui = MatrixUIDecoder()
            
            # The Telepathic Field Loop (Fluid Swarm)
            # Context is inherently maintained in the ambient vector space.
            while flow_active:
                # ---------------------------------------------------------
                # 1. Commander: Routing & Flow Evaluation
                # ---------------------------------------------------------
                print(f"  [\033[33mCommander\033[0m] Sensing Telepathic Field and Eternal Memory...")
                # In a pure fluid swarm, Commander injects a routing intent vector.
                # For this implementation, we use a hybrid state approach combined with vector drift.
                routing_intent = ambient_vector.clone()
                
                if current_stage == "planning":
                    print(f"  [\033[33mCommander\033[0m] Emitting routing intent: [REQUIRE_PLANNING]")
                elif current_stage == "implementation":
                    print(f"  [\033[33mCommander\033[0m] Emitting routing intent: [REQUIRE_IMPLEMENTATION]")
                elif current_stage == "translation":
                    print(f"  [\033[33mCommander\033[0m] Emitting routing intent: [REQUIRE_TRANSLATION]")
                
                # ---------------------------------------------------------
                # 2. Workers: Autonomous Activation
                # ---------------------------------------------------------
                if current_stage in ["planning", "implementation"]:
                    print(f"  [\033[36mWorkers\033[0m] Catching Intent Vector and Starting Telepathic Debate...")
                    
                    # OFF-LOAD TO WORKER VIA THUNDERBOLT RPC
                    if args.cluster_mode == 'master' and rpc is not None:
                        print(f"  [\033[36mThunderbolt RPC\033[0m] Offloading Swarm Debate to Worker Node...")
                        # Ensure we send float16 to match worker
                        rpc.send_tensor(ambient_vector.to(torch.float16))
                        print(f"  [\033[36mThunderbolt RPC\033[0m] Waiting for Worker to finish thinking...")
                        # Receive back the debate consensus
                        debate_vector = rpc.recv_tensor(dtype=torch.float16, shape=(1, 3840), device=device).to(torch.float32)
                        
                        # Update ambient space with worker consensus
                        ambient_vector = debate_vector.clone()
                        # Worker already ran Scout Execution, so we jump to translation
                        current_stage = "translation"
                        continue
                    
                    # LOCAL SWARM DEBATE (Fallback if no RPC)
                    worker_brain = JCrossBrain(worker_jgen, device)
                    debate_vector = ambient_vector.clone()
                    
                    # Workers debate freely in the latent space
                    for w_idx in range(1, 4):
                        role_name = f"Worker {w_idx}"
                        cognitive_anchor_text = None
                        
                        if w_idx == 1:
                            role_name = "Worker 1 (Architect)"
                            cognitive_anchor_text = "Analyze dependencies, define API usage, and plan step-by-step architecture."
                        elif w_idx == 2:
                            role_name = "Worker 2 (Dependency Manager)"
                            cognitive_anchor_text = "Ensure correct Swift API types, SceneKit/ARKit interactions, and module boundaries."
                        elif w_idx == 3:
                            role_name = "Worker 3 (Logic Optimizer)"
                            cognitive_anchor_text = "Refine the logic flow, ensure performance, and finalize the detailed blueprint."
                            
                        try:
                            # Encode the cognitive anchor
                            anchor_vector = global_coder.text_to_intent(cognitive_anchor_text)
                            # Align dimensions
                            if anchor_vector.shape[-1] != debate_vector.shape[-1]:
                                anchor_vector = torch.nn.functional.pad(anchor_vector, (0, debate_vector.shape[-1] - anchor_vector.shape[-1]))
                            
                            prev_debate = debate_vector.clone()
                            debate_vector, _ = worker_brain.think_internally(
                                debate_vector, 
                                thought_steps=max_steps, 
                                role_name=role_name, 
                                color_code="\033[36m",
                                cognitive_anchor=anchor_vector,
                                step_callback=global_coder.continuous_feedback_step
                            )
                            
                            # Continuous Telepathic Synchronisation (Latent Gating)
                            # The Coder continuously listens and applies its linguistic base law (context_prompt)
                            # to the Worker's vector, naturally maintaining context through vector interference.
                            debate_vector = global_coder.align_intent(debate_vector, original_prompt=context_prompt)
                            
                            features = matrix_ui.record_step(role_name, debate_vector, prev_debate)
                            print(f"  {matrix_ui.render_terminal_progress(role_name, features, '\033[36m')}")
                        except Exception as e:
                            print(f"  [\033[31mError\033[0m] Worker {w_idx} failed: {e}")
                            
                    worker_brain.close()
                    del worker_brain
                    purge_memory()
                    
                    # Update the ambient space with Worker's consensus
                    ambient_vector = debate_vector.clone()
                    memory_bank.diffuse_thought(ambient_vector, intensity=1.0, flag_label=f"Worker Consensus ({current_stage})", agent_id=w_idx)
                    
                    # State transition logic
                    current_stage = "translation"
                
                # ---------------------------------------------------------
                # 3. Telepathic Coder: Translation (Human-in-the-loop & Final Output)
                # ---------------------------------------------------------
                elif current_stage == "translation":
                    print(f"\n============================================================")
                    print(f"[\033[95mVerantyx Code Synthesis\033[0m] Handing over to Lossless Telepathic Coder")
                    print(f"============================================================\n")
                    
                    try:
                        # Fluid Cognitive Anchoring: We no longer artificially dampen the norm.
                        # We pass the raw ambient_vector directly to the Coder. The Coder will 
                        # dynamically determine whether to code or explain based on the vector's semantic axes.
                        decode_vector = ambient_vector.clone()
                        
                        # Phase 2.5: RAG Text Retrieval Wiring
                        # Extract exact text/knowledge from Eternal Memory to ground Gemma's vision
                        retrieved_knowledge = memory_bank.retrieve_context_text(decode_vector, workspace_dir, k=3)
                        final_prompt = f"Context: {context_prompt}\n"
                        if retrieved_knowledge:
                            final_prompt += f"\n[Project Knowledge / Best Practices]:\n{retrieved_knowledge}\n"
                        
                        # Coder Blindness & Fluid Role Switching:
                        # We pass a single fluid prompt containing the original context (and now retrieved knowledge)
                        inferred_text = global_coder.synthesize_code(decode_vector, subtask_prompt=final_prompt)
                        # If the output doesn't contain code blocks, the vector was low-res (planning phase)
                        if "```" not in inferred_text:
                            print(f"\n  [\033[33mTelepathic Coder\033[0m] Translated Swarm Plan:\n{inferred_text}\n")
                            
                            # [COMMANDER REVIEW - Latent Push]
                            print(f"  [\033[33mCommander\033[0m] Reviewing the submitted plan based on Cloud Assessment: '{cloud_assessment}'...")
                            plan_lower = inferred_text.lower()
                            has_steps = "step 1" in plan_lower or "phase 1" in plan_lower or "architecture" in plan_lower or "1." in plan_lower
                            plan_length = len(inferred_text)
                            
                            is_approved = True
                            reject_reason = ""
                            
                            if cloud_assessment == "大":
                                if plan_length < 300 or not has_steps:
                                    is_approved = False
                                    reject_reason = "Project Complexity: 大 (Large). The plan lacks detailed step-by-step architecture for a large project."
                            elif cloud_assessment == "中":
                                if plan_length < 100 or not has_steps:
                                    is_approved = False
                                    reject_reason = "Project Complexity: 中 (Medium). The plan lacks basic steps and structure."
                            
                            if not is_approved:
                                print(f"  [\033[31mCommander Rejected\033[0m] {reject_reason}")
                                print(f"  [\033[33mCommander\033[0m] Pushing feedback vector to Workers: 'Rewrite the blueprint with detailed step-by-step tasks.'")
                                feedback_intent = global_coder.text_to_intent("Rewrite the blueprint with detailed step-by-step tasks appropriate for the project size.")
                            else:
                                print(f"  [\033[32mCommander Approved\033[0m] The plan meets the requirements. Pushing Implementation intent.")
                                # Push intent to implement code instead of appending a text tag
                                feedback_intent = global_coder.text_to_intent("The plan is approved. Now implement the exact swift code for the project requirements.")
                                
                            combined = ambient_vector + feedback_intent
                            c_norm = combined.norm().item()
                            ambient_vector = (combined / (c_norm + 1e-6)) * 1.0 # Maintain stable norm (removed * 25.0)
                            current_stage = "implementation"
                            
                            print(f"  [\033[35mSwarm Memory\033[0m] Vector updated. Continuing debate...")
                            continue
                        else:
                            # It's final high-resolution code
                            import re
                            
                            # First, check if the output contains any file tags
                            # The pattern looks for "// file: path" or "# file: path"
                            pattern = r'(?://|#)\s*(?:file|path):\s*([a-zA-Z0-9_/\.\-]+)'
                            parts = re.split(pattern, inferred_text, flags=re.IGNORECASE)
                            
                            # Check if the code generation was exhausted (incomplete)
                            code_blocks = inferred_text.count("```")
                            is_complete = (code_blocks % 2 == 0) and (code_blocks > 0)
                            
                            # Use a local static variable equivalent to track retries to prevent infinite loops
                            if not hasattr(global_coder, 'retry_count'):
                                global_coder.retry_count = 0
                                
                            mode = "a" if global_coder.retry_count > 0 else "w"
                            
                            if len(parts) == 1:
                                # Fallback: No file tags found, dump everything to a default file
                                ext = ".swift"
                                if "python" in inferred_text.lower(): ext = ".py"
                                output_filename = f"verantyx_synthesis_fluid{ext}"
                                full_path = os.path.join(workspace_dir, output_filename)
                                os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else workspace_dir, exist_ok=True)
                                
                                save_text = inferred_text
                                if mode == "a":
                                    save_text = re.sub(r'^```[a-zA-Z]*\n', '', save_text)
                                    
                                with open(full_path, mode) as f:
                                    f.write(save_text)
                                print(f"  [\033[94mTelepathic Coder\033[0m] Chunk decoded and written to default: {full_path}")
                                
                            else:
                                # Parse multiple files autonomously
                                for i in range(1, len(parts), 2):
                                    filename = parts[i].strip().lstrip('/')
                                    content = parts[i+1]
                                    
                                    if '..' in filename or not filename:
                                        continue
                                        
                                    # Clean up markdown code blocks surrounding the content
                                    content = content.lstrip()
                                    content = re.sub(r'^```[a-zA-Z]*\n', '', content)
                                    content = re.sub(r'```\s*$', '', content.rstrip())
                                    
                                    full_path = os.path.join(workspace_dir, filename)
                                    os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else workspace_dir, exist_ok=True)
                                    
                                    with open(full_path, mode) as f:
                                        f.write(content + "\n")
                                    print(f"  [\033[92mAutonomous Architect\033[0m] Designed & Generated file: {full_path}")
                            
                            if not is_complete and global_coder.retry_count < 3:
                                print("  [\033[35mAutoregressive Loop\033[0m] Vector intent exhausted. Feeding back to Swarm for continuation...")
                                # Renew ambient vector with the latest context
                                active_ambient_vector = global_coder.text_to_intent(context_prompt + "\nFeedback: Continue coding from where you left off.") * 1.0 # Maintain stable norm (removed * 15.0)
                                ambient_vector = active_ambient_vector.clone()
                                current_stage = "translation" # Route directly back to Coder to continue writing, skipping workers
                                global_coder.retry_count += 1
                                continue
                            else:
                                print("  [\033[32mSwarm\033[0m] Subtask declared complete.")
                                active_ambient_vector = None # Reset for next completely new task
                                context_prompt = ""
                                flow_active = False
                                global_coder.retry_count = 0
                                break
                        purge_memory()
                    except Exception as e:
                        import traceback
                        print(f"  [\033[31mError\033[0m] Coder Synthesis Failed: {e}")
                        traceback.print_exc()
                        flow_active = False
                        break
            
        except KeyboardInterrupt:
            print(f"\n  [\033[33mSystem\033[0m] Ctrl+C detected. Initiating Emergency Hibernation...")
            try:
                memory_bank.hibernate()
            except Exception as e:
                print(f"  [\033[31mError\033[0m] Failed to hibernate memory: {e}")
            
            # Save GUI session state index
            try:
                state_file = os.path.join(workspace_dir, ".verantyx_chrono", "session_state.json")
                os.makedirs(os.path.dirname(state_file), exist_ok=True)
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "vector_count": len(memory_bank.zone_b_index),
                        "status": "Hibernated successfully (Zone B dumped)."
                    }, f, indent=2)
            except Exception:
                pass
                
            print("Exiting Verantyx Shell. Vector spaces safely preserved.")
            sys.exit(0)
                
        except EOFError:
            break
        except Exception as e:
            print(f"[\033[31mERROR\033[0m] {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Verantyx Shell")
    parser.add_argument("--cluster-mode", choices=['master', 'worker'], default=None, help="Run in distributed Thunderbolt cluster mode")
    parser.add_argument("--worker-ip", default="10.0.0.2", help="IP address of the worker Mac")
    args = parser.parse_args()
    
    if args.cluster_mode == 'worker':
        print("\033[36m[System] Launching Worker Daemon for Thunderbolt Distributed Inference...\033[0m")
        from telepathic_coder_experimental import TelepathicCoder
        # Pass dummy workspace, worker daemon doesn't write files
        coder = TelepathicCoder(os.getcwd(), cluster_mode='worker')
        coder.run_worker_daemon()
        sys.exit(0)
        
    # Inject args into builtins to pass them implicitly to main() without changing main's signature
    import builtins
    builtins.args = args
    asyncio.run(main())
