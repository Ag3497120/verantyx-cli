import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_map

class MyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.lin = nn.Linear(10, 10)
        
m = MyModel()
print("Before:", m.lin.weight.dtype)
leaves = tree_map(lambda x: x.astype(mx.float16) if isinstance(x, mx.array) else x, m.parameters())
m.update(leaves)
print("After update:", m.lin.weight.dtype)
