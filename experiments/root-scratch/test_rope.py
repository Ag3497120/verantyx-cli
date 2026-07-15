import torch
x = torch.arange(8).float().reshape(1, 1, 1, 8)
# Let's say rot_dim = 8
# rope_cache = [cos_0, sin_0, cos_1, sin_1, cos_2, sin_2, cos_3, sin_3]
rope_cache = torch.tensor([0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6]).view(1, 1, 4, 2)
# The GLM logic:
b, np, sq, hn = x.size(0), x.size(1), x.size(2), x.size(3)
xshaped = x.reshape(b, np, sq, 4, 2)
rope_cache = rope_cache.view(-1, 1, sq, xshaped.size(3), 2)
x_out2 = torch.stack(
    [
        xshaped[..., 0] * rope_cache[..., 0] - xshaped[..., 1] * rope_cache[..., 1],
        xshaped[..., 1] * rope_cache[..., 0] + xshaped[..., 0] * rope_cache[..., 1],
    ],
    -1,
)
print("GLM output:")
print(x_out2.flatten())

