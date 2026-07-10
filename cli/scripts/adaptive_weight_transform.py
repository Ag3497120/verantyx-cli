import os
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from copy import deepcopy

class AdaptiveWeightTransform:
    def __init__(self, model_id, safety_threshold=0.99):
        self.model_id = model_id
        self.safety_threshold = safety_threshold
        print(f"[*] Initializing AdaptiveWeightTransform with model: {model_id}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        # Load model into RAM
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32, device_map="cpu")
        
        self.backup_states = {}
        
    def _get_baseline_logits(self, text):
        """Runs the un-modified model and returns the final logits for comparison."""
        inputs = self.tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.logits

    def selective_reformat_layer(self, layer_idx, strategy="bypass_ffn"):
        """
        Applies JCross structural reformatting to a single layer.
        """
        print(f"\n[*] Applying JCross Transform [{strategy}] to Layer {layer_idx}...")
        layers = self.model.model.layers
        if layer_idx < 0 or layer_idx >= len(layers):
            print(f"[-] Invalid layer index: {layer_idx}")
            return False
            
        target_layer = layers[layer_idx]
        
        # Backup the layer state for rollback
        self.backup_states[layer_idx] = deepcopy(target_layer.state_dict())
        
        if strategy == "residual_short_circuit":
            # Completely bypass the layer's contribution to the residual stream
            # We still run it to maintain HF KV Cache structure, but we force the 
            # output hidden states to exactly match the input hidden states.
            class ShortCircuitLayer(nn.Module):
                def __init__(self, original_layer):
                    super().__init__()
                    self.original_layer = original_layer
                def forward(self, hidden_states, *args, **kwargs):
                    # Run original to get past_key_values etc.
                    outputs = self.original_layer(hidden_states, *args, **kwargs)
                    if isinstance(outputs, tuple):
                        return (hidden_states,) + outputs[1:]
                    else:
                        return hidden_states
            
            layers[layer_idx] = ShortCircuitLayer(target_layer)
            print(f"[+] Layer {layer_idx} mathematically short-circuited (100% bypass).")
            
        elif strategy == "bypass_ffn":
            # Force the FFN outputs to zero, essentially bypassing the MLP component's contribution
            # to the residual stream.
            class BypassFFN(nn.Module):
                def __init__(self, original_mlp):
                    super().__init__()
                    self.original_mlp = original_mlp
                def forward(self, x):
                    # Return zeros of the same shape as input
                    return torch.zeros_like(x)
                    
            target_layer.mlp = BypassFFN(target_layer.mlp)
            print(f"[+] Layer {layer_idx} FFN bypassed (Sparse masking applied).")
            
        else:
            print(f"[-] Unknown strategy: {strategy}")
            return False
            
        return True

    def validate_against_original(self, layer_idx, test_text, original_logits):
        """
        Validates the modified model's output against the original logits.
        """
        print(f"[*] Validating transformation on Layer {layer_idx}...")
        inputs = self.tokenizer(test_text, return_tensors="pt")
        
        with torch.no_grad():
            modified_outputs = self.model(**inputs)
        
        mod_logits = modified_outputs.logits
        
        # Flatten and compute Cosine Similarity of the final sequence logits
        flat_orig = original_logits.view(-1, original_logits.shape[-1])
        flat_mod = mod_logits.view(-1, mod_logits.shape[-1])
        
        cos_sim = F.cosine_similarity(flat_orig, flat_mod, dim=1).mean().item()
        
        print(f"[>] Cosine Similarity: {cos_sim:.6f} (Threshold: {self.safety_threshold:.2f})")
        
        if cos_sim >= self.safety_threshold:
            print("[+] SUCCESS: Transformation passed safety check. Wiring is unbroken.")
            return True
        else:
            print("[-] FAILED: Safety threshold breached. Gradient flow/Wiring corrupted.")
            return False

    def rollback(self, layer_idx):
        """Reverts the layer to its original state."""
        print(f"[*] Rolling back Layer {layer_idx} to original state...")
        layers = self.model.model.layers
        
        if layer_idx in self.backup_states:
            # If we swapped the module entirely (short_circuit), we need to unwrap it
            if hasattr(layers[layer_idx], 'original_layer'):
                layers[layer_idx] = layers[layer_idx].original_layer
            elif hasattr(layers[layer_idx].mlp, 'original_mlp'):
                layers[layer_idx].mlp = layers[layer_idx].mlp.original_mlp
                
            # Restore state dict just to be safe
            layers[layer_idx].load_state_dict(self.backup_states[layer_idx])
            del self.backup_states[layer_idx]
            print(f"[+] Rollback complete for Layer {layer_idx}.")
        else:
            print(f"[-] No backup found for Layer {layer_idx}.")

def main():
    parser = argparse.ArgumentParser(description="JCross Adaptive Weight Transform (Phase 2)")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-0.5B", help="Model ID")
    parser.add_argument("--text", type=str, default="Verantyx JCross creates 6-axis MoE routing for LLMs.", help="Validation text")
    args = parser.parse_args()
    
    transform = AdaptiveWeightTransform(args.model)
    
    # 1. Baseline Extraction
    print("\n--- Baseline Extraction ---")
    orig_logits = transform._get_baseline_logits(args.text)
    
    # 2. Test Layer 18: Residual Short Circuit
    print("\n--- Experiment 1: Layer 18 (Residual Short Circuit) ---")
    if transform.selective_reformat_layer(18, strategy="residual_short_circuit"):
        if not transform.validate_against_original(18, args.text, orig_logits):
            transform.rollback(18)
    
    # Reset model to clean state
    if 18 in transform.backup_states:
        transform.rollback(18)
        
    # 3. Test Layer 12: Bypass FFN
    print("\n--- Experiment 2: Layer 12 (Bypass FFN) ---")
    if transform.selective_reformat_layer(12, strategy="bypass_ffn"):
        if not transform.validate_against_original(12, args.text, orig_logits):
            transform.rollback(12)
            
    # Test a critical layer (Layer 0) as a negative control
    if 12 in transform.backup_states:
         transform.rollback(12)
         
    print("\n--- Experiment 3: Layer 0 Negative Control (Bypass FFN) ---")
    if transform.selective_reformat_layer(0, strategy="bypass_ffn"):
        if not transform.validate_against_original(0, args.text, orig_logits):
            transform.rollback(0)

if __name__ == "__main__":
    main()
