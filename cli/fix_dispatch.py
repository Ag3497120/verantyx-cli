import re
with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'r') as f:
    content = f.read()

content = re.sub(
    r'encoder\.setThreadgroupMemoryLength\(64 \* MemoryLayout<Float>\.stride, index: 0\)\s*'
    r'encoder\.dispatchThreadgroups\(MTLSizeMake\(64, 1, 1\), threadsPerThreadgroup: MTLSizeMake\(64, 1, 1\)\)',
    
    r'encoder.setThreadgroupMemoryLength(128 * MemoryLayout<Float>.stride, index: 0)\n'
    r'                        encoder.dispatchThreadgroups(MTLSizeMake(32, 1, 1), threadsPerThreadgroup: MTLSizeMake(128, 1, 1))',
    content
)

with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'w') as f:
    f.write(content)
