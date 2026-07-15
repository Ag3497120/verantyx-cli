import re
layer_groups = {}
keys = ["model.layers.0", "model.layers.1", "model.layers.2", "model.layers.10", "model.layers.11"]
for k in keys:
    match = re.search(r"model\.layers\.(\d+)", k)
    layer_groups[match.group(1)] = k # oops! match.group(1) is a string!
layer_groups = dict(sorted(layer_groups.items()))
print(layer_groups)
