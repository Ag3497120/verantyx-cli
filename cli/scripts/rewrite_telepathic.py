import os

with open("cli/scripts/telepathic_coder_hybrid.py", "r") as f:
    content = f.read()

# 1. Optimize HF Model Loading
old_hf_load = """hf_model = AutoModelForCausalLM.from_pretrained(model_path_hf, torch_dtype=torch.float16, local_files_only=True)"""
new_hf_load = """try:
                    hf_model = AutoModelForCausalLM.from_pretrained(
                        model_path_hf, 
                        torch_dtype=torch.float16, 
                        local_files_only=True,
                        low_cpu_mem_usage=True,
                        device_map="mps"
                    )
                except Exception as e:
                    self.log(f"MPS loading failed, falling back to CPU: {e}")
                    hf_model = AutoModelForCausalLM.from_pretrained(
                        model_path_hf, 
                        torch_dtype=torch.float16, 
                        local_files_only=True,
                        low_cpu_mem_usage=True,
                        device_map="cpu"
                    )"""
content = content.replace(old_hf_load, new_hf_load)

# 2. Fix IntentLogitsProcessor
old_processor = """class IntentLogitsProcessor(LogitsProcessor):
                def __init__(self, intent_logits, initial_strength=0.5, decay_rate=0.9):
                    self.intent_logits = intent_logits
                    self.current_strength = initial_strength
                    self.decay_rate = decay_rate

                def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
                    # Blend the Swarm's intent softly into the model's predictions
                    blended_scores = scores + (self.intent_logits * self.current_strength)
                    # Decay the strength so the model relies more on its own context over time
                    self.current_strength *= self.decay_rate
                    return blended_scores

            logits_processor = LogitsProcessorList([
                IntentLogitsProcessor(intent_logits=intent_logits, initial_strength=0.3, decay_rate=0.95)
            ])"""

new_processor = """class IntentLogitsProcessor(LogitsProcessor):
                def __init__(self, intent_logits, initial_strength=0.15, decay_rate=0.8):
                    self.intent_logits = intent_logits
                    self.current_strength = initial_strength
                    self.decay_rate = decay_rate

                def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
                    if self.current_strength < 0.01:
                        return scores
                        
                    # To prevent grammar destruction (hallucination), we only boost tokens
                    # that the LLM already considers syntactically valid (Top 50).
                    top_k = 50
                    top_k_scores, top_k_indices = torch.topk(scores, top_k, dim=-1)
                    
                    # Create a mask of negative infinity
                    safe_mask = torch.full_like(scores, -float('inf'))
                    # Unmask the top-k indices
                    safe_mask.scatter_(-1, top_k_indices, 0.0)
                    
                    # Apply intent only to those safe tokens
                    safe_intent = self.intent_logits.clone()
                    safe_intent[safe_mask == -float('inf')] = 0.0
                    
                    blended_scores = scores + (safe_intent * self.current_strength)
                    self.current_strength *= self.decay_rate
                    return blended_scores

            logits_processor = LogitsProcessorList([
                IntentLogitsProcessor(intent_logits=intent_logits, initial_strength=0.15, decay_rate=0.85)
            ])"""
content = content.replace(old_processor, new_processor)

with open("cli/scripts/telepathic_coder.py", "w") as f:
    f.write(content)
print("Rewrite complete.")
