import re
with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'r') as f:
    content = f.read()

# Fix L2Norm offset and dimensions
content = re.sub(
    r'encoder\.setBuffer\(outQkvBuffer, offset: 6144 \* 4, index: 0\)\s*'
    r'var numKHeads: UInt32 = 32\s*'
    r'var headKDim: UInt32 = 64',
    
    r'encoder.setBuffer(outQkvBuffer, offset: 0, index: 0)\n'
    r'                        var numKHeads: UInt32 = 32\n'
    r'                        var headKDim: UInt32 = 128',
    content
)

# Fix recurrent step parameters
content = re.sub(
    r'var numVHeads: UInt32 = 48\s*'
    r'var headVDim: UInt32 = 128\s*'
    r'encoder\.setBytes\(&numVHeads, length: 4, index: 8\)\s*'
    r'encoder\.setBytes\(&numKHeads, length: 4, index: 9\)\s*'
    r'encoder\.setBytes\(&headKDim, length: 4, index: 10\)\s*'
    r'encoder\.setBytes\(&headVDim, length: 4, index: 11\)',
    
    r'var numVHeads: UInt32 = 48\n'
    r'                            var realNumKHeads: UInt32 = 16\n'
    r'                            var headVDim: UInt32 = 128\n'
    r'                            encoder.setBytes(&numVHeads, length: 4, index: 8)\n'
    r'                            encoder.setBytes(&realNumKHeads, length: 4, index: 9)\n'
    r'                            encoder.setBytes(&headKDim, length: 4, index: 10)\n'
    r'                            encoder.setBytes(&headVDim, length: 4, index: 11)',
    content
)

with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'w') as f:
    f.write(content)
