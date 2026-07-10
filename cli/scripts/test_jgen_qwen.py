import torch
import struct
import time
import sys
import os

# --- ANSI Color Codes ---
C_CYAN   = "\033[36m"
C_PURPLE = "\033[35m"
C_SYS    = "\033[90m"
C_RESET  = "\033[0m"

class JCrossBrain:
    def __init__(self, jgen_path, device="mps"):
        self.device = device
        self.layers = []
        
        print(f"{C_SYS}[System] Loading neural patterns from {os.path.basename(jgen_path)}...{C_RESET}")
        start_time = time.time()
        
        with open(jgen_path, "rb") as f:
            magic = f.read(4)
            if magic != b"JGEN": raise ValueError("Invalid magic bytes")
            f.read(4)
            tensor_count = struct.unpack("<I", f.read(4))[0]
            
            for _ in range(tensor_count):
                name_len = struct.unpack("<H", f.read(2))[0]
                name = f.read(name_len).decode('utf-8', errors='ignore')
                t_type = struct.unpack("<B", f.read(1))[0]
                
                if t_type == 1:
                    rows, cols, rank = struct.unpack("<I I I", f.read(12))
                    
                    U = torch.frombuffer(f.read(rows * rank * 2), dtype=torch.float16).reshape(rows, rank).to(device)
                    S = torch.frombuffer(f.read(rank * 2), dtype=torch.float16).to(device)
                    V = torch.frombuffer(f.read(cols * rank * 2), dtype=torch.float16).reshape(cols, rank).to(device)
                    mx = torch.frombuffer(f.read(cols * 2), dtype=torch.float16).to(device)
                    my = torch.frombuffer(f.read(rows * 2), dtype=torch.float16).to(device)
                    
                    self.layers.append({
                        "name": name,
                        "U": U, "S": S, "V": V, "mx": mx, "my": my,
                        "cols": cols, "rows": rows
                    })
                    
        print(f"{C_SYS}[System] Fully loaded {len(self.layers)} layers into VRAM in {time.time()-start_time:.2f}s.{C_RESET}")
        if len(self.layers) > 0:
            print(f"{C_SYS}[System] Expected Hidden Dimension: {self.layers[0]['cols']}{C_RESET}")
        
    def forward_latent(self, x, role_name="Qwen-0.5B", color_code=C_CYAN):
        h = x.clone()
        norm_epsilon = 1e-6
        
        print(f"\n{C_PURPLE}>>> Commencing Latent Propagation (Vector Space)...{C_RESET}")
        with torch.no_grad():
            for i, layer in enumerate(self.layers):
                if h.shape[-1] != layer["cols"]:
                    continue 
                
                # --- Anti-Vanishing Mechanism (RMSNorm) ---
                variance = h.pow(2).mean(-1, keepdim=True)
                normed_h = h * torch.rsqrt(variance + norm_epsilon)
                    
                # --- JCross Mapping ---
                z = torch.matmul(normed_h * layer["mx"], layer["V"])
                z_scaled = z * layer["S"]
                
                # --- Multi-Banding ---
                rank = z_scaled.shape[-1]
                half_rank = rank // 2
                
                main_z = z_scaled[..., :half_rank]
                back_z = z_scaled[..., half_rank:]
                
                curr_main = main_z
                for _ in range(3):
                    gate = torch.sigmoid(curr_main)
                    curr_main = torch.nn.functional.silu(main_z * gate)
                
                absorbed_back = torch.nn.functional.gelu(back_z)
                
                z_out_main = main_z + curr_main
                z_out_back = back_z + absorbed_back
                z_out = torch.cat([z_out_main, z_out_back], dim=-1)
                
                temp = torch.matmul(z_out, layer["U"].T)
                out = temp + layer["my"]
                
                if out.shape == h.shape:
                    h = h + out
                else:
                    h = out 
                
                # --- Visual Feedback (Matrix Style) ---
                leak_vals = h[0, :6].cpu().float().numpy()
                formatted_leak = " ".join([f"{v:>7.3f}" for v in leak_vals])
                
                time.sleep(0.01) # Slightly slower for observation
                sys.stdout.write(f"{color_code}[{role_name} | Layer {i:03d}] {formatted_leak} ...{C_RESET}\n")
                sys.stdout.flush()
                
        print(f"{C_PURPLE}>>> Propagation Complete.{C_RESET}\n")
        return h


if __name__ == "__main__":
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"=== Qwen-0.5B JCross Standalone Tester ===")
    print(f"Device: {device}")
    
    jgen_path = "/Users/motonishikoudai/verantyx-cli/cli/qwen_0.5b.jgen"
    if not os.path.exists(jgen_path):
        print(f"[Error] File not found: {jgen_path}")
        sys.exit(1)
        
    brain = JCrossBrain(jgen_path, device)
    
    if len(brain.layers) == 0:
        print("[Error] No valid layers found in the .jgen file.")
        sys.exit(1)
        
    hidden_dim = brain.layers[0]["cols"]
    
    while True:
        try:
            print(f"\n{C_SYS}Options:{C_RESET}")
            print("  [1] Inject random thought vector (Simulate unknown concept)")
            print("  [2] Inject zero vector (Simulate empty state)")
            print("  [exit] Quit")
            choice = input(f"Select option> ").strip()
            
            if choice.lower() in ['exit', 'quit']:
                break
                
            if choice == '1':
                print(f"{C_SYS}Generating random thought vector [1, {hidden_dim}]...{C_RESET}")
                input_vector = torch.randn(1, hidden_dim, dtype=torch.float16, device=device)
            elif choice == '2':
                print(f"{C_SYS}Generating zero vector [1, {hidden_dim}]...{C_RESET}")
                input_vector = torch.zeros(1, hidden_dim, dtype=torch.float16, device=device)
            else:
                continue
                
            # Perform propagation
            start_calc = time.time()
            output_vector = brain.forward_latent(input_vector, role_name="Qwen-0.5B", color_code=C_CYAN)
            elapsed = time.time() - start_calc
            
            print(f"{C_SYS}Input Norm:  {torch.norm(input_vector).item():.4f}{C_RESET}")
            print(f"{C_SYS}Output Norm: {torch.norm(output_vector).item():.4f}{C_RESET}")
            print(f"{C_SYS}Time taken:  {elapsed:.2f}s{C_RESET}")
            
        except KeyboardInterrupt:
            break
            
    print("Exiting.")
