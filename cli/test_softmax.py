import numpy as np

logits_array = np.zeros(248320, dtype=np.float32)
exp_logits = np.exp(logits_array - np.max(logits_array))
probs = exp_logits / np.sum(exp_logits)
print("Uniform max prob:", np.max(probs))

logits_array = np.random.randn(248320).astype(np.float32) * 1e-12
exp_logits = np.exp(logits_array - np.max(logits_array))
probs = exp_logits / np.sum(exp_logits)
print("Tiny max prob:", np.max(probs))
