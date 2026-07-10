import re
with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'r') as f:
    content = f.read()

content = re.sub(
    r'var qSizeRope: UInt32 = 24 \* 256',
    r'var qSizeRope: UInt32 = 48 * 256',
    content
)

content = re.sub(
    r'var numQHeads: UInt32 = 24\s*'
    r'var numKvHeads: UInt32 = 4\s*'
    r'encoder\.setBytes\(&seqLen, length: 4, index: 3\)\s*'
    r'encoder\.setBytes\(&layerIdx, length: 4, index: 4\)\s*'
    r'encoder\.setBytes\(&numQHeads, length: 4, index: 5\)\s*'
    r'encoder\.setBytes\(&numKvHeads, length: 4, index: 6\)\s*'
    r'var headDim: UInt32 = 256\s*'
    r'encoder\.setBytes\(&headDim, length: 4, index: 7\)\s*'
    r'encoder\.setThreadgroupMemoryLength\(4096 \* MemoryLayout<Float>\.stride, index: 0\)\s*'
    r'encoder\.dispatchThreadgroups\(MTLSizeMake\(24, 1, 1\), threadsPerThreadgroup: MTLSizeMake\(256, 1, 1\)\)',
    
    r'var numQHeads: UInt32 = 48\n'
    r'                        var numKvHeads: UInt32 = 4\n'
    r'                        encoder.setBytes(&seqLen, length: 4, index: 3)\n'
    r'                        encoder.setBytes(&layerIdx, length: 4, index: 4)\n'
    r'                        encoder.setBytes(&numQHeads, length: 4, index: 5)\n'
    r'                        encoder.setBytes(&numKvHeads, length: 4, index: 6)\n'
    r'                        var headDim: UInt32 = 256\n'
    r'                        encoder.setBytes(&headDim, length: 4, index: 7)\n'
    r'                        encoder.setThreadgroupMemoryLength(4096 * MemoryLayout<Float>.stride, index: 0)\n'
    r'                        encoder.dispatchThreadgroups(MTLSizeMake(48, 1, 1), threadsPerThreadgroup: MTLSizeMake(256, 1, 1))',
    content
)

with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'w') as f:
    f.write(content)
