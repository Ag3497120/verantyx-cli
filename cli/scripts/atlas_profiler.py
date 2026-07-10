import os
import json
import argparse
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from tqdm import tqdm

class ActivationAtlasProfiler:
    """Phase 7: Activation Atlas Mapping (Internal Topological Profiler)"""
    def __init__(self, model_id):
        self.model_id = model_id
        print(f"[*] Loading model {model_id} for Activation Atlas Profiling...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        # Load in float32 on cpu to avoid MPS bfloat16 bugs
        device = "cpu"
        self.device = device
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            torch_dtype=torch.float32, 
            device_map=device
        )
        
        self.num_layers = len(self.model.model.layers)
        
        # Stats dictionaries
        # For each layer, we want to record the "activation frequency" of the FFN intermediate dimensions
        self.ffn_dim_importance = {}
        # We also want to record the variance of the residual stream to find attenuation points
        self.residual_variance = {}
        
        self.hooks = []
        
    def _register_hooks(self):
        def make_ffn_hook(layer_idx):
            def hook(module, input, output):
                # For Qwen, the MLP output is the final down_proj. 
                # But we want the intermediate dimension (after gate/up).
                # The input to down_proj is exactly the intermediate representation.
                # input[0] shape: [batch, seq_len, intermediate_dim]
                intermediate_activation = input[0].float()
                
                # Measure how strongly each dimension fired (mean absolute value across batch/seq)
                dim_strength = torch.mean(torch.abs(intermediate_activation), dim=(0, 1))
                
                if layer_idx not in self.ffn_dim_importance:
                    self.ffn_dim_importance[layer_idx] = torch.zeros_like(dim_strength)
                    
                # Accumulate strength
                self.ffn_dim_importance[layer_idx] += dim_strength
                
            return hook

        def make_residual_hook(layer_idx):
            def hook(module, input, output):
                # input[0] is the hidden state entering the layer
                in_state = input[0].float()
                # Measure variance of the stream to find attenuation
                var = torch.var(in_state).item()
                
                if layer_idx not in self.residual_variance:
                    self.residual_variance[layer_idx] = []
                self.residual_variance[layer_idx].append(var)
                
            return hook

        for idx, layer in enumerate(self.model.model.layers):
            # Hook the down_proj to capture the intermediate state entering it
            self.hooks.append(layer.mlp.down_proj.register_forward_hook(make_ffn_hook(idx)))
            # Hook the layer itself to capture the residual stream entering it
            self.hooks.append(layer.register_forward_hook(make_residual_hook(idx)))

    def build_atlas(self, prompts):
        print(f"[*] Building Activation Atlas using {len(prompts)} diverse prompts...")
        self._register_hooks()
        
        for text in tqdm(prompts, desc="Profiling Prompts"):
            inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
            with torch.no_grad():
                self.model(**inputs)
                
        # Cleanup
        for h in self.hooks:
            h.remove()
            
    def export_route_map(self, output_path="route_map.json"):
        print(f"[*] Exporting Route Map to {output_path}...")
        route_map = {
            "metadata": {
                "model": self.model_id,
                "description": "Activation Atlas for JCross Predictive Routing",
                "num_layers": self.num_layers
            },
            "layers": {}
        }
        
        for z in range(self.num_layers):
            # Normalize dim_importance to create a "Static Score" between 0 and 1
            if z in self.ffn_dim_importance:
                raw_strength = self.ffn_dim_importance[z]
                max_strength = torch.max(raw_strength)
                if max_strength > 0:
                    normalized = raw_strength / max_strength
                else:
                    normalized = raw_strength
                
                # Subsample or group into JCross blocks (e.g. 64-dim tiles) if needed
                # For simplicity, we save the raw normalized array
                dim_scores = normalized.cpu().numpy().tolist()
            else:
                dim_scores = []
                
            # Average variance
            if z in self.residual_variance:
                avg_var = sum(self.residual_variance[z]) / len(self.residual_variance[z])
            else:
                avg_var = 1.0
                
            route_map["layers"][str(z)] = {
                "ffn_dim_scores": dim_scores,
                "expected_variance": avg_var
            }
            
        with open(output_path, "w") as f:
            json.dump(route_map, f)
            
        print("[+] Route map successfully created!")

def main():
    parser = argparse.ArgumentParser(description="JCross Activation Atlas Profiler")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-0.5B", help="HuggingFace Model ID")
    parser.add_argument("--out", type=str, default="route_map.json", help="Output JSON path")
    args = parser.parse_args()
    
    # A diverse set of prompts designed to activate reasoning, math, language, code, and trivia
    calibration_prompts = [
        "What is the capital of France?",
        "Translate the following sentence to Japanese: The quick brown fox jumps over the lazy dog.",
        "Solve this equation: 2x + 5 = 15. What is x?",
        "def quicksort(arr):",
        "Write a poem about a lonely robot exploring Mars.",
        "Explain the theory of general relativity in simple terms.",
        "The mitochondria is the powerhouse of the cell because",
        "```cpp\n#include <iostream>\nint main() {\n",
        "List 5 psychological biases and explain them.",
        "A recipe for chocolate chip cookies:",
        "In a dystopian future, a hacker discovers a flaw in the megacorporation's mainframe.",
        "Evaluate the philosophical arguments for free will."
    ] * 2  # Duplicate to increase signal slightly
    
    profiler = ActivationAtlasProfiler(args.model)
    profiler.build_atlas(calibration_prompts)
    profiler.export_route_map(args.out)

if __name__ == "__main__":
    main()
