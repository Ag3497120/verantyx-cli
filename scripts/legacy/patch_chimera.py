import re

with open('cli/scripts/chimera_swarm_experimental.py', 'r') as f:
    content = f.read()

# 1. Add dictionary loading to JCrossBrain.__init__
init_patch = """
        self.device = device
        self.layers = []
        
        # --- CHIMERA: Load 27B Static Dictionaries ---
        self.chimera_dicts = []
        import glob
        import os
        dict_files = glob.glob("cli/scripts/qwen_jcross_dicts/real_layer_*_down_proj.pt")
        dict_files.sort(key=lambda x: int(os.path.basename(x).split('_')[2]))
        if dict_files:
            print(f"\\033[96m  [Chimera] Loading {len(dict_files)} 27B Static Dictionaries...\\033[0m")
            for df in dict_files:
                self.chimera_dicts.append(torch.load(df, map_location=self.device))
        else:
            print(f"\\033[93m  [Chimera] No dicts found!\\033[0m")
"""
content = re.sub(r'self\.device = device\s+self\.layers = \[\]', init_patch, content, count=1)

# 2. Modify forward_latent to inject the 27B knowledge
forward_patch = """
                if h.shape[-1] != layer["cols"]:
                    continue 
                    
                # ==============================================================
                # [CHIMERA INJECTION] 27B Static Dictionary Lookup
                # ==============================================================
                if len(self.chimera_dicts) > 0:
                    dict_idx = int(i * (len(self.chimera_dicts) / len(self.layers)))
                    if dict_idx < len(self.chimera_dicts):
                        c_dict = self.chimera_dicts[dict_idx]
                        # 0.5B hidden is ~896. 27B needs 17408. Pad with zeros.
                        c_in_dim = c_dict["V"].shape[0]  # 17408
                        c_out_dim = c_dict["mx"].shape[1] # 3584 (U's shape is [128, 3584])
                        
                        pad_size = c_in_dim - h.shape[-1]
                        if pad_size > 0:
                            h_padded = torch.nn.functional.pad(h, (0, pad_size), "constant", 0)
                        else:
                            h_padded = h[..., :c_in_dim]
                            
                        # Query the 27B Dictionary (using its V, S, mx, C_valve)
                        # Forward through dict: z = h @ V
                        # Note: V is [17408, 128], mx is [128, 3584]
                        z_chimera = torch.matmul(h_padded.to(torch.float16), c_dict["V"].to(torch.float16))
                        if "C_valve" in c_dict:
                            z_chimera = torch.matmul(z_chimera, c_dict["C_valve"].to(torch.float16))
                        z_chimera = torch.nn.functional.silu(z_chimera)
                        
                        # Apply puzzle lock (zero-shot static memory recall)
                        z_chimera_scaled = z_chimera * c_dict["S"].to(torch.float16)
                        
                        out_chimera = torch.matmul(z_chimera_scaled, c_dict["mx"].to(torch.float16))
                        
                        # Truncate back to 0.5B dimension (896) and blend it
                        # The knowledge is "squeezed" into the lower dimensions
                        out_chimera_trunc = out_chimera[..., :h.shape[-1]]
                        
                        # Blend the 27B knowledge into the 0.5B reasoning stream (20% injection)
                        h = h + (out_chimera_trunc * 0.2)
                # ==============================================================

                # Retrieve past state for this layer if available
"""
content = re.sub(r'if h\.shape\[-1\] != layer\["cols"\]:\s+continue\s+# Retrieve past state', forward_patch, content, count=1)

with open('cli/scripts/chimera_swarm_experimental.py', 'w') as f:
    f.write(content)
print("Patched!")
