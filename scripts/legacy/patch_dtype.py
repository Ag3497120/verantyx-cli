with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()
import re
text = text.replace('logits = torch.matmul(raw_thought_embeds, vocab_embeddings.T)', 'logits = torch.matmul(raw_thought_embeds.to(vocab_embeddings.dtype), vocab_embeddings.T)')
with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)
