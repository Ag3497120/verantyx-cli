import torch
import numpy as np

# Simulate extraction
W = torch.randn(10, 20).float()
rows, cols = 10, 20
rank = 5

U, S, Vh = torch.linalg.svd(W, full_matrices=False)
U_r = U[:, :rank].half()
S_r = S[:rank].half()
V_r = Vh[:rank, :].T.half()

U_bytes = U_r.numpy().tobytes()
S_bytes = S_r.numpy().tobytes()
V_bytes = V_r.numpy().tobytes()

# Simulate loading
U_data = np.frombuffer(U_bytes, dtype=np.float16).reshape(rows, rank)
S_data = np.frombuffer(S_bytes, dtype=np.float16)
V_data = np.frombuffer(V_bytes, dtype=np.float16).reshape(cols, rank)

U_p = torch.from_numpy(U_data).float()
S_p = torch.from_numpy(S_data).float()
V_p = torch.from_numpy(V_data).float()

x = torch.randn(3, 20).float()

# Original computation
y_orig = x @ W.T

# Extracted computation
W_approx = U_p @ torch.diag(S_p) @ V_p.T
y_approx = x @ W_approx.T

# Fast forward computation
h = x @ V_p
y_fast = (h * S_p) @ U_p.T

print("Orig vs Approx error:", torch.max(torch.abs(y_orig - y_approx)).item())
print("Approx vs Fast error:", torch.max(torch.abs(y_approx - y_fast)).item())

