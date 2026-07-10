import re
with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'r') as f:
    content = f.read()

content = content.replace(
"""                        var numKHeads: UInt32 = 32
                        var headKDim: UInt32 = 128
                        encoder.setBytes(&numKHeads, length: 4, index: 1)""",
"""                        var totalQkHeads: UInt32 = 32
                        var numQHeadsLinear: UInt32 = 16
                        var headKDim: UInt32 = 128
                        encoder.setBytes(&numQHeadsLinear, length: 4, index: 1)"""
)

with open('Sources/VeraCore/Backends/VeraMetalBackend.swift', 'w') as f:
    f.write(content)
