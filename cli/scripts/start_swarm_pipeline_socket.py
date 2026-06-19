import subprocess
import sys
import argparse
import socket
import threading
import json
import time

def monitor_node_stdout(node_id, process, sys_stdout):
    for line in iter(process.stdout.readline, b''):
        decoded_line = line.decode('utf-8').strip()
        if decoded_line:
            try:
                data = json.loads(decoded_line)
                if "jsonrpc" in data:
                    sys_stdout.write(decoded_line + "\\n")
                    sys_stdout.flush()
            except Exception:
                pass

def monitor_ide_stdin(processes_dict, sys_stdin):
    while True:
        line = sys_stdin.readline()
        if not line:
            break
        decoded_line = line.strip()
        if decoded_line:
            try:
                data = json.loads(decoded_line)
                node_id = data.get("id")
                if node_id is not None and node_id in processes_dict:
                    node_process = processes_dict[node_id]
                    node_process.stdin.write((decoded_line + "\\n").encode('utf-8'))
                    node_process.stdin.flush()
            except Exception as e:
                sys.stderr.write(f"[Orchestrator] Error parsing IDE input: {e}\\n")

def send_to_node_and_wait_text(port, text):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', port))
        client.sendall(text.encode('utf-8'))
        
        # Temporary server to receive the text reply (since our physical node script sends to `send_port`)
        # Wait, the node connects to `send_port` to send the response. We must set up a listener.
    except Exception as e:
        sys.stderr.write(f"[*] Connection error: {e}\\n")

def main():
    parser = argparse.ArgumentParser(description="Start Socket-based JCross Vector Pipeline Swarm")
    parser.add_argument("--prompt", type=str, default="A simple HTML button with red text.", help="Initial prompt for Commander")
    parser.add_argument("--nodes", type=int, default=10, help="Total number of physical worker nodes")
    parser.add_argument("--base_port", type=int, default=10000, help="Base port for socket communication")
    parser.add_argument("--sub_commanders", type=int, default=3, help="Number of sub-commanders for discussion layer")
    args = parser.parse_args()

    num_nodes = args.nodes
    prompt = args.prompt
    base_port = args.base_port
    num_sub = args.sub_commanders

    sys.stderr.write(f"[*] Starting {num_nodes} physical Qwen 0.5B nodes + {num_sub} SubCommanders...\\n")

    # 0. Preload the model to prevent download race conditions and timeouts
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    preload_script = os.path.join(script_dir, "preload_model.py")
    sys.stderr.write("[*] Verifying/Downloading model weights to cache...\\n")
    subprocess.run(["python3", preload_script], check=True)

    processes = {}
    
    # 1. Start SubCommanders (Nodes 101, 102, 103...)
    sub_personas = []
    if num_sub >= 1:
        sub_personas.append((101, "You are a Creative Advisor. Provide an innovative and out-of-the-box approach."))
    if num_sub >= 2:
        sub_personas.append((102, "You are a Critical Advisor. Focus on edge cases, potential failures, and logical flaws."))
    if num_sub >= 3:
        sub_personas.append((103, "You are a Pragmatic Advisor. Provide the fastest, most reliable, and simplest solution."))
        
    for sid, persona in sub_personas:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        node_script = os.path.join(script_dir, "qwen_physical_node_socket.py")
        
        cmd = ["python3", node_script, 
               "--node_id", str(sid), "--role", "sub_commander", 
               "--listen_port", str(base_port + sid), 
               "--send_port", str(base_port + sid + 1000),
               "--persona", persona]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        processes[sid] = p

    # 2. Start Pipeline Nodes (0: Commander, 1..N-2: Workers, N-1: Final)
    for i in range(num_nodes):
        role = "worker"
        if i == 0: role = "commander"
        if i == num_nodes - 1: role = "final"
        
        # Use node_script correctly
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        node_script = os.path.join(script_dir, "qwen_physical_node_socket.py")
        
        cmd = ["python3", node_script, 
               "--node_id", str(i), "--role", role,
               "--listen_port", str(base_port + i), 
               "--send_port", str(base_port + i + 1)]
        
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        processes[i] = p
        
        t = threading.Thread(target=monitor_node_stdout, args=(i, p, sys.stdout), daemon=True)
        t.start()

    ide_t = threading.Thread(target=monitor_ide_stdin, args=(processes, sys.stdin), daemon=True)
    ide_t.start()

    time.sleep(10) # Wait for all models to load

    current_topic = prompt
    merged_plan = ""

    # --- DISCUSSION LAYER ---
    if num_sub > 0:
        sys.stderr.write("[*] Initiating Discussion Layer...\\n")
        
        # Pre-bind receiving sockets to avoid Errno 48 on multiple turns
        sub_recv_socks = {}
        for sid, _ in sub_personas:
            recv_port = base_port + sid + 1000
            recv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            recv_sock.bind(('127.0.0.1', recv_port))
            recv_sock.listen(1)
            sub_recv_socks[sid] = recv_sock
            
        commander_recv_port = base_port + 2000
        commander_recv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        commander_recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        commander_recv_sock.bind(('127.0.0.1', commander_recv_port))
        commander_recv_sock.listen(1)
        
        for turn in range(3): # Max 3 discussion turns
            sys.stderr.write(f"\\n--- Discussion Turn {turn+1} ---\\n")
            sub_opinions = []
            
            # A. Get opinions from SubCommanders
            for sid, _ in sub_personas:
                recv_sock = sub_recv_socks[sid]
                
                # Send prompt with retry logic (models may take a while to load)
                max_retries = 30
                connected = False
                client = None
                for r in range(max_retries):
                    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        client.connect(('127.0.0.1', base_port + sid))
                        connected = True
                        break
                    except ConnectionRefusedError:
                        client.close()
                        time.sleep(2)
                
                if not connected:
                    sys.stderr.write(f"[*] Timeout waiting for SubCommander {sid}\\n")
                    continue
                    
                client.sendall(current_topic.encode('utf-8'))
                client.close()
                
                # Wait for text reply
                conn, addr = recv_sock.accept()
                opinion = conn.recv(16384).decode('utf-8')
                sub_opinions.append(f"Opinion from SubCommander {sid}:\\n{opinion}")
                conn.close()
                
                sys.stderr.write(f"[*] SubCommander {sid} responded.\\n")
                
            combined_opinions = "\\n\\n".join(sub_opinions)
            
            # B. Ask Commander to Merge
            sys.stderr.write("[*] Commander is merging opinions...\\n")
            
            # Send merge request to Commander
            req = {
                "type": "merge",
                "prompt": f"Original Topic: {prompt}\\n\\nOpinions:\\n{combined_opinions}",
                "send_port": commander_recv_port
            }
            
            commander_connected = False
            client = None
            for r in range(30):
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    client.connect(('127.0.0.1', base_port)) # Node 0
                    commander_connected = True
                    break
                except ConnectionRefusedError:
                    client.close()
                    time.sleep(2)
                    
            if not commander_connected:
                sys.stderr.write("[*] Timeout waiting for Commander\\n")
                break
                
            client.sendall(json.dumps(req).encode('utf-8'))
            client.close()
            
            # Wait for Commander's text reply
            conn, addr = commander_recv_sock.accept()
            merged_plan = conn.recv(32768).decode('utf-8')
            conn.close()
            
            sys.stderr.write(f"\\n[Commander Merge Result]:\\n{merged_plan}\\n\\n")
            
            if "[RE-DISCUSS]" in merged_plan:
                current_topic = f"We have a problem in the plan. Commander says:\\n{merged_plan}\\n\\nPlease discuss and fix this."
                sys.stderr.write("[*] Commander requested RE-DISCUSS. Starting next turn...\\n")
            else:
                sys.stderr.write("[*] Discussion merged successfully. Proceeding to Execution Phase.\\n")
                break
                
        commander_recv_sock.close()
    else:
        sys.stderr.write("[*] Discussion Layer skipped (sub_commanders=0).\\n")
        merged_plan = f"User Request: {prompt}\\n(Discussion bypassed)"

    # --- EXECUTION PHASE ---
    sys.stderr.write("[*] Pipeline is running Execution Phase. Waiting for final result...\\n")
    
    # 最終ノード(Node 9)の出力を受け取るためのサーバーソケットを起動
    final_port = base_port + num_nodes
    final_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    final_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    final_server.bind(('127.0.0.1', final_port))
    final_server.listen(1)

    # Send execute request to Commander (Worker Node 1)
    req = {
        "type": "execute",
        "prompt": f"Original Request: {prompt}\\n\\nApproved Plan:\\n{merged_plan}",
        "send_port": base_port + 1 # Target Node 1 (Worker)
    }
    
    exec_connected = False
    client = None
    for r in range(30):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(('127.0.0.1', base_port))
            exec_connected = True
            break
        except Exception:
            client.close()
            time.sleep(2)
            
    if not exec_connected:
        sys.stderr.write("[*] Failed to connect to Commander for Execution Phase.\\n")
        return
        
    client.sendall(json.dumps(req).encode('utf-8'))
    client.close()

    # 最終結果の受信待機
    conn, addr = final_server.accept()
    final_text = conn.recv(4096).decode('utf-8')
    conn.close()
    final_server.close()
    
    # 最終結果をIDE(Swift)へJSONで返す
    final_response = {
        "status": "success",
        "result": f"[Discussion Plan]\\n{merged_plan}\\n\\n[Final Result]\\n{final_text}"
    }
    sys.stdout.write(json.dumps(final_response) + "\\n")
    sys.stdout.flush()

    sys.stderr.write("\\n[*] Swarm Pipeline execution completed.\\n")
    
    # 終了処理
    for pid, p in processes.items():
        p.terminate()

if __name__ == "__main__":
    main()
