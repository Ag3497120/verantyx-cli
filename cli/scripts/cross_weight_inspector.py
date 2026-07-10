import os
import argparse
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from tqdm import tqdm
from safetensors import safe_open

class CROSSWeightInspector:
    """Static Weight Inspector (Phase 1)"""
    def __init__(self, safetensors_path):
        self.path = safetensors_path

    def project_to_3d_lattice(self):
        layer_stats = {}
        with safe_open(self.path, framework="pt", device="cpu") as f:
            for key in f.keys():
                if "layers" not in key or "weight" not in key: continue
                parts = key.split(".")
                try:
                    z_depth = int(parts[parts.index("layers") + 1])
                except (ValueError, IndexError):
                    continue
                if z_depth not in layer_stats: layer_stats[z_depth] = {}
                tensor = f.get_tensor(key)
                comp_name = parts[-2]
                layer_stats[z_depth][comp_name] = {
                    "shape": list(tensor.shape),
                    "variance": torch.var(tensor).item(),
                    "sparsity": (torch.abs(tensor) < 1e-4).float().mean().item(),
                    "magnitude": torch.abs(tensor).mean().item()
                }
        self.layer_stats = layer_stats

class CROSSDynamicInspector:
    """Dynamic Activation Inspector (Phase 1.5)"""
    def __init__(self, model_id):
        self.model_id = model_id
        print(f"[*] Loading model {model_id} for dynamic activation analysis...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32, device_map="cpu")
        
        self.activation_stats = {}
        self.hooks = []
        
    def _register_hooks(self):
        # We want to hook the output of FFN (specifically the activation function output like SiLU/GELU if accessible, 
        # or just the up_proj/gate_proj outputs) and the residual stream (the input and output of each decoder layer).
        
        def make_ffn_hook(layer_idx):
            def hook(module, input, output):
                # output might be a tuple
                val = output[0] if isinstance(output, tuple) else output
                # Calculate dynamic sparsity (percentage of values close to 0)
                sparsity = (torch.abs(val) < 1e-3).float().mean().item()
                
                if layer_idx not in self.activation_stats:
                    self.activation_stats[layer_idx] = {}
                self.activation_stats[layer_idx]['ffn_activation_sparsity'] = sparsity
            return hook

        def make_residual_hook(layer_idx):
            def hook(module, input, output):
                # input[0] is the hidden state entering the layer
                # output[0] is the hidden state leaving the layer
                in_state = input[0]
                out_state = output[0] if isinstance(output, tuple) else output
                
                # Calculate Cosine Similarity to see if the layer actually changed the stream
                # Flatten the sequence and batch dims
                in_flat = in_state.view(-1, in_state.shape[-1])
                out_flat = out_state.view(-1, out_state.shape[-1])
                
                cos_sim = F.cosine_similarity(in_flat, out_flat, dim=1).mean().item()
                
                if layer_idx not in self.activation_stats:
                    self.activation_stats[layer_idx] = {}
                self.activation_stats[layer_idx]['residual_cosine_sim'] = cos_sim
            return hook

        # Attach to the model layers
        # For Qwen/Llama, layers are in model.model.layers
        layers = self.model.model.layers
        for idx, layer in enumerate(layers):
            # Hook the FFN output (usually MLP)
            self.hooks.append(layer.mlp.register_forward_hook(make_ffn_hook(idx)))
            # Hook the entire layer to capture residual change
            self.hooks.append(layer.register_forward_hook(make_residual_hook(idx)))

    def run_forward_pass(self, text):
        print(f"[*] Running forward pass with input: '{text}'")
        self._register_hooks()
        
        inputs = self.tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            self.model(**inputs)
            
        # Cleanup hooks
        for h in self.hooks:
            h.remove()
            
    def display_dynamic_metrics(self):
        print("\n=== Dynamic Activation Metrics ===")
        print("Legend:")
        print(" - FFN Sparsity: High means the layer's knowledge is rarely used (good candidate for JCross bypass).")
        print(" - Residual Cosine Sim: High (near 1.0) means the layer did nothing (good candidate for JCross bypass).")
        
        sorted_layers = sorted(self.activation_stats.keys())
        for z in sorted_layers:
            stats = self.activation_stats[z]
            ffn_spars = stats.get('ffn_activation_sparsity', 0.0)
            cos_sim = stats.get('residual_cosine_sim', 0.0)
            
            flag = "[! BYPASS CANDIDATE]" if (ffn_spars > 0.5 or cos_sim > 0.99) else ""
            print(f"Layer Z={z:02d} | FFN Sparsity: {ffn_spars:5.2%} | Residual CosSim: {cos_sim:6.4f} {flag}")


def main():
    parser = argparse.ArgumentParser(description="JCross 3D Lattice Dynamic Inspector")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-0.5B", help="HuggingFace Model ID")
    parser.add_argument("--text", type=str, default="Hello, how can I use JCross for 3D tensor mapping?", help="Input text for dynamic activation")
    args = parser.parse_args()
    
    inspector = CROSSDynamicInspector(args.model)
    inspector.run_forward_pass(args.text)
    inspector.display_dynamic_metrics()

if __name__ == "__main__":
    main()
