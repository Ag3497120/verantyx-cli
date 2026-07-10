import torch
import torch.nn as nn

conv = nn.Conv1d(1, 1, kernel_size=4, bias=False)
conv.weight.data = torch.tensor([[[1.0, 2.0, 3.0, 4.0]]])
x = torch.tensor([[[10.0]]]) # seq_len = 1
out = conv(torch.nn.functional.pad(x, (3, 0)))
print(out)
