import re
with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'r') as f:
    content = f.read()

content = re.sub(
    r'encoder\.dispatchThreadgroups\(MTLSizeMake\(\(6144/2 \+ 63\)/64, 1, 1\), threadsPerThreadgroup: MTLSizeMake\(64, 1, 1\)\)',
    r'encoder.dispatchThreadgroups(MTLSizeMake((12288/2 + 63)/64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))',
    content
)

with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'w') as f:
    f.write(content)
