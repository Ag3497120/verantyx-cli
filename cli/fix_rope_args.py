import re
with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'r') as f:
    content = f.read()

content = re.sub(
    r'var qSizeRope: UInt32 = 48 \* 256\s*'
    r'var kSizeRope: UInt32 = 4 \* 256\s*'
    r'var headDimRope: UInt32 = 256\s*'
    r'var posRope: UInt32 = currentPos\s*'
    r'encoder\.setBytes\(&qSizeRope, length: 4, index: 2\)\s*'
    r'encoder\.setBytes\(&kSizeRope, length: 4, index: 3\)',
    
    r'var qSizeRope: UInt32 = 48\n'
    r'                        var kSizeRope: UInt32 = 4\n'
    r'                        var headDimRope: UInt32 = 256\n'
    r'                        var posRope: UInt32 = currentPos\n'
    r'                        encoder.setBytes(&qSizeRope, length: 4, index: 2)\n'
    r'                        encoder.setBytes(&kSizeRope, length: 4, index: 3)',
    content
)

with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'w') as f:
    f.write(content)
