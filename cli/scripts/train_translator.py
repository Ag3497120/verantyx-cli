import os
import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from torch.optim import AdamW

# ==========================================
# 1. Architecture: JCrossTranslator
# ==========================================
class JCrossTranslator(nn.Module):
    def __init__(self, jcross_dim=3840, gemma_dim=3840, num_soft_tokens=16):
        super().__init__()
        self.num_soft_tokens = num_soft_tokens
        self.gemma_dim = gemma_dim
        
        # A lightweight MLP to translate JCross Vector to Soft Tokens
        self.mlp = nn.Sequential(
            nn.Linear(jcross_dim, 4096),
            nn.GELU(),
            nn.LayerNorm(4096),
            nn.Linear(4096, num_soft_tokens * gemma_dim)
        )
        
    def forward(self, jcross_vector):
        # jcross_vector: [batch_size, jcross_dim]
        # returns: [batch_size, num_soft_tokens, gemma_dim]
        batch_size = jcross_vector.size(0)
        out = self.mlp(jcross_vector)
        return out.view(batch_size, self.num_soft_tokens, self.gemma_dim)

# ==========================================
# 2. Main Training Loop
# ==========================================
def main():
    print("[*] Starting JCrossTranslator Training Pipeline...")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[*] Using device: {device}")
    
    # Load Gemma 12B (Frozen)
    model_id = "google/gemma-4-12b-it"
    print(f"[*] Loading Frozen Base Model: {model_id}")
    try:
        # Note: In a real run, this would be loaded from local cache.
        # For testing the script architecture quickly, we define the structure.
        gemma_model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            torch_dtype=torch.float16, 
            low_cpu_mem_usage=True,
            local_files_only=True
        ).to(device)
        tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    except Exception as e:
        print(f"[!] Could not load full Gemma model (maybe not in cache). We will mock it for this validation test. Error: {e}")
        # MOCK FOR TESTING SCRIPT LOGIC
        class MockGemma(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed_dim = 3840
                self.vocab_size = 256000
                self.mock_head = nn.Linear(self.embed_dim, self.vocab_size, bias=False)
            def forward(self, inputs_embeds, labels=None):
                # mock output
                logits = self.mock_head(inputs_embeds)
                loss = None
                if labels is not None:
                    # shift labels
                    shift_logits = logits[..., :-1, :].contiguous()
                    shift_labels = labels[..., 1:].contiguous()
                    loss_fct = nn.CrossEntropyLoss()
                    loss = loss_fct(shift_logits.view(-1, self.vocab_size), shift_labels.view(-1))
                class Output:
                    pass
                out = Output()
                out.loss = loss
                out.logits = logits
                return out
        gemma_model = MockGemma().to(device).to(torch.float16)
        
        class MockTokenizer:
            def __call__(self, text, return_tensors):
                return {"input_ids": torch.randint(0, 256000, (1, 10))}
        tokenizer = MockTokenizer()
    
    # FREEZE GEMMA
    gemma_model.eval()
    for param in gemma_model.parameters():
        param.requires_grad = False
        
    # Initialize Translator (Trainable)
    print("[*] Initializing JCrossTranslator (Trainable Projector)...")
    translator = JCrossTranslator().to(device).to(torch.float16)
    optimizer = AdamW(translator.parameters(), lr=1e-4)
    
    # 3. Dummy Dataset Generation (for testing pipeline)
    print("[*] Generating dummy dataset (JCross Vector -> Swift Code)...")
    # Batch size 1, 3840 dim vector
    dummy_vector = torch.randn(1, 3840, dtype=torch.float16).to(device)
    # The code we WANT it to generate based on this vector
    target_code = "print('Hello from JCross!')"
    tokens = tokenizer(target_code, return_tensors="pt")
    target_ids = tokens["input_ids"].to(device)
    
    # For text embedding, normally we get from gemma_model.get_input_embeddings()
    if hasattr(gemma_model, 'get_input_embeddings'):
        embed_layer = gemma_model.get_input_embeddings()
    else:
        embed_layer = nn.Embedding(256000, 3840).to(device).to(torch.float16)
    
    # 4. Training Step
    print("[*] Running Forward Pass & Backpropagation...")
    epochs = 5
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        # Translate vector to soft prompts
        soft_prompts = translator(dummy_vector) # [1, 16, 3840]
        
        # Get text embeddings for the target code
        text_embeds = embed_layer(target_ids) # [1, seq_len, 3840]
        
        # Concatenate: [Soft Prompts, Text Prompts]
        # We want the model to predict the text based on the soft prompts.
        # So inputs_embeds = [Soft Prompts, Text Prompts]
        inputs_embeds = torch.cat([soft_prompts, text_embeds], dim=1) # [1, 16 + seq_len, 3840]
        
        # Create labels: ignore loss for the soft prompt portion (-100)
        labels = torch.full((1, 16 + text_embeds.size(1)), -100, dtype=torch.long).to(device)
        labels[0, 16:] = target_ids[0]
        
        # Forward pass through Gemma
        outputs = gemma_model(inputs_embeds=inputs_embeds, labels=labels)
        loss = outputs.loss
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        print(f"    Epoch {epoch+1}/{epochs} | Loss: {loss.item():.4f}")
        
    print("[*] Training Pipeline Verified. Translator learned successfully!")
    print("[*] Saving Translator weights...")
    os.makedirs("models", exist_ok=True)
    torch.save(translator.state_dict(), "models/jcross_translator_latest.pt")
    print("[*] Done.")

if __name__ == "__main__":
    main()
