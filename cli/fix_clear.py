import re

with open("Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    code = f.read()

# Fix kOutBuffer clear
code = code.replace("clearBuffer(kOutBuffer, size: 4096, encoder: encoder)", "clearBuffer(kOutBuffer, size: 1024, encoder: encoder)")

# Add clear for qOutBuffer in the else branch
old_else = """                        } else {
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(qBlocks, inBuffer: normedSpineBuffer, outBuffer: qOutBuffer, encoder: encoder)
                        }"""

new_else = """                        } else {
                            encoder.setComputePipelineState(psoBlockMatMul)
                            clearBuffer(qOutBuffer, size: 12288, encoder: encoder)
                            dispatchBlocks(qBlocks, inBuffer: normedSpineBuffer, outBuffer: qOutBuffer, encoder: encoder)
                        }"""

code = code.replace(old_else, new_else)

with open("Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(code)

print("Fixed clearBuffer sizes")
