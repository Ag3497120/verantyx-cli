import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import sys

# --- ANSI Color Codes ---
C_QWEN   = "\033[36m"
C_SYS    = "\033[90m"
C_RESET  = "\033[0m"

class QwenTranslator:
    def __init__(self, model_id="Qwen/Qwen1.5-0.5B-Chat", device="mps"):
        self.device = device
        print(f"{C_SYS}[System] Loading {model_id} as Language Decoder...{C_RESET}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            torch_dtype=torch.float16,
            device_map=self.device
        )
        print(f"{C_SYS}[System] Decoder Loaded successfully.{C_RESET}")
        
    def decode_with_telepathy(self, intent_text: str, telepathy_vectors: torch.Tensor, max_length=150):
        """
        Soft Prompt Injection: Injects raw vectors into Qwen's embedding space.
        """
        inputs = self.tokenizer(intent_text, return_tensors="pt").to(self.device)
        input_ids = inputs["input_ids"]
        
        with torch.no_grad():
            word_embeddings = self.model.get_input_embeddings()(input_ids)
            
            tv = telepathy_vectors.to(self.device).to(torch.float16)
            if len(tv.shape) == 2:
                tv = tv.unsqueeze(0)
                
            # Align hidden dimensions
            if tv.shape[-1] != word_embeddings.shape[-1]:
                diff = word_embeddings.shape[-1] - tv.shape[-1]
                if diff > 0:
                    tv = torch.nn.functional.pad(tv, (0, diff))
                else:
                    tv = tv[..., :word_embeddings.shape[-1]]
            
            # Normalize vector scale to match Qwen's expected embedding scale
            tv_norm = torch.norm(tv, p=2, dim=-1, keepdim=True)
            we_norm_avg = torch.norm(word_embeddings, p=2, dim=-1).mean()
            tv = tv * (we_norm_avg / (tv_norm + 1e-6))
            
            # Concatenate
            combined_embeds = torch.cat([tv, word_embeddings], dim=1)
            
            # Bypass tie_word_embeddings issue
            original_tie = self.model.config.tie_word_embeddings
            self.model.config.tie_word_embeddings = False
            
            outputs = self.model.generate(
                inputs_embeds=combined_embeds,
                max_new_tokens=max_length,
                temperature=0.2,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            self.model.config.tie_word_embeddings = original_tie
            
        generated = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        return generated

    def chat_normally(self, prompt: str, max_length=150):
        """Normal text-based generation for comparison."""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_length,
            temperature=0.7,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        return self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()


if __name__ == "__main__":
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"=== Qwen-0.5B Decoder (Translator) Tester ===")
    
    # We use HuggingFace Qwen because .jgen lacks the vocabulary/LM_head needed for language generation
    translator = QwenTranslator(model_id="Qwen/Qwen1.5-0.5B-Chat", device=device)
    
    hidden_dim = translator.model.config.hidden_size
    print(f"{C_SYS}[System] Qwen hidden dimension is {hidden_dim}. Ready for translation.{C_RESET}")
    
    while True:
        try:
            print(f"\n{C_SYS}Options:{C_RESET}")
            print("  [1] Chat Normally (Text -> Text)")
            print("  [2] Decode Telepathy (Vector + Text -> Text)")
            print("  [exit] Quit")
            choice = input("Select option> ").strip()
            
            if choice.lower() in ['exit', 'quit']:
                break
                
            if choice == '1':
                user_text = input(f"{C_QWEN}You: {C_RESET}")
                prompt = f"<|im_start|>user\n{user_text}<|im_end|>\n<|im_start|>assistant\n"
                response = translator.chat_normally(prompt)
                print(f"{C_QWEN}Qwen-0.5B: {response}{C_RESET}")
                
            elif choice == '2':
                # Simulate a JCross vector coming from the Swarm
                print(f"{C_SYS}Generating simulated swarm intent vector [1, {hidden_dim}]...{C_RESET}")
                simulated_vector = torch.randn(1, hidden_dim, dtype=torch.float16, device=device)
                
                trigger_text = "<|im_start|>system\nTranslate the preceding intent vector into a command.<|im_end|>\n<|im_start|>assistant\n"
                response = translator.decode_with_telepathy(trigger_text, simulated_vector)
                
                print(f"{C_QWEN}Qwen-0.5B (Translated from Vector): {response}{C_RESET}")
                
            else:
                continue
                
        except KeyboardInterrupt:
            break
            
    print("Exiting.")
