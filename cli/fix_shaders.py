import os
import re

files = [
    "Sources/VeraCore/Backends/Shaders.metal",
    "Sources/VeraCore/Backends/LMHeadShaders.metal",
    "Sources/VeraCore/Backends/AttentionShaders.metal",
    "Sources/VeraCore/Backends/LinearAttentionShaders.metal"
]

def revert_bfloat16(content):
    content = content.replace("bfloat16_to_float32(", "(float)(")
    # Need to remove the extra closing parenthesis from bfloat16_to_float32
    # But wait, it's safer to use regex
    content = re.sub(r'bfloat16_to_float32\((.*?)\)', r'(float)(\1)', content)
    content = content.replace("uint16_t*", "half*")
    content = content.replace("uint16_t", "half")
    return content

for file in files:
    with open(file, 'r') as f:
        content = f.read()
    new_content = revert_bfloat16(content)
    with open(file, 'w') as f:
        f.write(new_content)
    print(f"Fixed {file}")

