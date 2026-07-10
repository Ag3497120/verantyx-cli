import re
with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'r') as f:
    content = f.read()

content = re.sub(
    r'encoder\.setComputePipelineState\(psoAdd\)\s*'
    r'encoder\.setBuffer\(zSpineBuffer, offset: 0, index: 0\)\s*'
    r'encoder\.setBuffer\(downOutBuffer, offset: 0, index: 1\)\s*'
    r'encoder\.setBuffer\(zSpineBuffer, offset: 0, index: 2\)\s*'
    r'var downSize: UInt32 = UInt32\(dim\)\s*'
    r'encoder\.setBytes\(&downSize, length: 4, index: 3\)',
    
    r'encoder.setComputePipelineState(psoAdd)\n'
    r'                        encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)\n'
    r'                        encoder.setBuffer(downOutBuffer, offset: 0, index: 1)\n'
    r'                        var downSize: UInt32 = UInt32(dim)\n'
    r'                        encoder.setBytes(&downSize, length: 4, index: 2)',
    content
)

with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'w') as f:
    f.write(content)
