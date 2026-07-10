import re

files = [
    "Sources/VeraCore/Backends/Shaders.metal",
    "Sources/VeraCore/Backends/LMHeadShaders.metal",
    "Sources/VeraCore/Backends/AttentionShaders.metal",
    "Sources/VeraCore/Backends/LinearAttentionShaders.metal"
]

for file in files:
    with open(file, 'r') as f:
        content = f.read()
    content = content.replace("(float)(", "(float)")
    
    # Remove the bfloat16_to_float32 definition if it got messed up
    content = re.sub(r'inline float \(float\)half bfloat_val\) {.*?return as_type<float>\(bits\);\n}', '', content, flags=re.DOTALL)
    
    with open(file, 'w') as f:
        f.write(content)

