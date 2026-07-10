            self._mmap_handle.close()
            self._mmap_handle = None

    def think_internally(self, ambient_context, thought_steps=20, role_name="Worker", color_code=C_WORKER, cognitive_anchor=None, step_callback=None):
        """
        Runs the autoregressive sequence generation inside the JCross latent space.
        If cognitive_anchor (string) is provided, it is converted to a vector and blended into the initial thought
        to enforce role-based planning and dependency management.
        If step_callback is provided, it leaks the current thought vector at each step (for Coder continuous feedback).
        """
        import torch
        print(f"{color_code}  [{role_name}] 思考プロセス開始 (JCross Latent Inference...){C_RESET}")
        
        current_hidden = ambient_context.clone()
        
        # Inject Role-Based Cognitive Anchor
        if cognitive_anchor is not None:
            # Normalize and blend the anchor to steer the debate
            anchor_norm = cognitive_anchor.norm().item()
            c_norm = current_hidden.norm().item()
            normalized_anchor = (cognitive_anchor / (anchor_norm + 1e-6)) * c_norm
            current_hidden = current_hidden * 0.99 + normalized_anchor * 0.01
            
        jcross_states = None
        generated_tokens = []
        
        print(f"{color_code}  [{role_name}] Thinking internally... ", end="")
        import sys
        sys.stdout.flush()
        
        with torch.no_grad():
            step = 0
            energy_delta = 1.0
            prev_hidden = current_hidden
            cumulative_uncertainty = 0.0
            saturation_counter = 0  # To detect if the thought has converged (Cos > 0.998)
            
            # Allow deeper thinking by lowering energy threshold and increasing saturation limit based on thought_steps
            max_saturation = max(3, thought_steps // 5)
            while step < thought_steps and energy_delta > 0.01 and saturation_counter < max_saturation:
                print(f"    [DEBUG] Starting step {step+1}/{thought_steps} (energy_delta: {energy_delta:.4f}, sat: {saturation_counter}/{max_saturation})", flush=True)
                # --- Ambient Telepathy: Leak thought to Coder ---
                if step_callback is not None:
                    feedback_vector = step_callback(current_hidden, step)
                    if feedback_vector is not None:
                        # Feed the Coder's correction back into the Worker's thought state
                        current_hidden = current_hidden + feedback_vector
                        

                # We DO NOT pass the vector through forward_latent (328 layers) here.
                # Doing so recursively destroys the Raw Embeddings.
                # Instead, the Swarm modifies the Raw Embeddings geometrically.
                # current_hidden = current_hidden + cognitive_shift_etc (handled via anchor)
                
                # We simulate the JCross state by mixing the vector directly
                current_hidden = current_hidden * 0.98 + prev_hidden * 0.02
                
                # Calculate Topological Coherence (Energy Delta)
                # Geometric binding between the previous thought and the current thought
                bound_energy = prev_hidden * torch.roll(current_hidden, shifts=1, dims=-1)
                current_energy = bound_energy.sum().item()
                # To simulate stabilization, energy_delta drops as thoughts align
                # (A simple proxy: difference between current vector norm and previous)
                energy_delta = torch.norm(current_hidden - prev_hidden).item() / (torch.norm(prev_hidden).item() + 1e-6)
                cumulative_uncertainty += energy_delta
                
                prev_hidden = current_hidden
                step += 1
                
                # Predict next token internally
                if getattr(self, 'final_norm_weight', None) is not None:
                    norm_epsilon = 1e-6
                    variance = current_hidden.pow(2).mean(-1, keepdim=True)
                    normed_hidden = current_hidden * torch.rsqrt(variance + norm_epsilon) * (1.0 + self.final_norm_weight)
                else:
                    normed_hidden = current_hidden
                
                if getattr(self, 'lm_head_weight', None) is not None:
                    logits = torch.matmul(normed_hidden, self.lm_head_weight.T)
                else:
                    hidden_size = current_hidden.shape[-1]
                    lm_head = torch.nn.Linear(hidden_size, 32000, bias=False, dtype=current_hidden.dtype).to(self.device)
                    logits = lm_head(current_hidden)
                
                # Apply strict ASCII mask to prevent internal Word Salad
                if not hasattr(self, 'allowed_token_mask'):
                    try:
                        from transformers import AutoTokenizer
                        import os
                        model_path = "Qwen/Qwen2.5-0.5B-Instruct"
                        tokenizer = AutoTokenizer.from_pretrained(model_path)
                        
                        vocab_size = logits.shape[-1]
                        mask = torch.full((vocab_size,), float('-inf'), device=self.device)
                        for t_id in range(vocab_size):
                            raw_token = tokenizer.convert_ids_to_tokens(t_id)
                            if raw_token is None or "<0x" in raw_token:
                                continue
                            t_str_clean = raw_token.replace(' ', '').replace('\u2581', '')
                            if t_id < 256 or all(32 <= ord(c) < 127 for c in t_str_clean if c):
                                mask[t_id] = 0.0
                        self.allowed_token_mask = mask
                    except:
                        self.allowed_token_mask = torch.zeros(logits.shape[-1], device=self.device)
                        
                # Move to CPU to prevent MPS Trace/BPT trap 5 crashes during NaN handling and sampling
                # Squeeze the sequence dimension to ensure logits is 2D: (batch_size, vocab_size)
                if logits.dim() == 2:
                    logits = logits.cpu().float()
                else:
                    logits = logits[:, -1, :].cpu().float()
                logits = torch.nan_to_num(logits, nan=0.0, posinf=100.0, neginf=-100.0)
                
                # Apply mask on CPU
                mask = self.allowed_token_mask.cpu().float()
                logits = logits + mask
                
                # Simple penalty to avoid repeating internal loops
                for token_id in set(generated_tokens[-10:]):
                    logits[0, token_id] -= 1.0
                
