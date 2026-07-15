import torch
import time
from cli.scripts.telepathic_coder import TelepathicCoder

print("Loading coder...")
coder = TelepathicCoder("/Users/motonishikoudai/verantyx-cli")
print("Generating dummy latent...")
dummy_latent = torch.randn(1, 4096, dtype=torch.float16, device="mps")
print("Synthesizing code...")
coder.synthesize_code(dummy_latent, prompt="Test prompt")
