with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

patch = """        let router_names = [
            format!("model.layers.{}.mlp.router.weight", layer),
            format!("model.layers.{}.mlp.gate.weight", layer)
        ];"""

import re
content = re.sub(r'        let router_names = \[format!\("model\.layers\.\{\}\.mlp\.router\.weight", layer\)\];', patch, content)

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
