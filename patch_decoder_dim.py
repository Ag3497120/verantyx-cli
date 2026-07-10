with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()
import re
# Replace the block that sets decoder_dim
text = re.sub(r'decoder_dim = 1024\n\s*if getattr\(self\.decoder_brain, \'layers\', None\) and len\(self\.decoder_brain\.layers\) > 0:\n\s*decoder_dim = self\.decoder_brain\.layers\[0\]\[\'cols\'\]', r'decoder_dim = self.hf_model.config.hidden_size', text)
with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)
