import re

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    code = f.read()

# Revert the bad change
code = code.replace("""                    private func clearBuffer(_ buffer: MTLBuffer, size: Int, encoder: MTLComputeCommandEncoder) {
        encoder.setComputePipelineState(psoClearBuffer)
        encoder.setBuffer(buffer, offset: 0, index: 0)
        let gridSize = MTLSizeMake((size + 63) / 64, 1, 1)
        let groupSize = MTLSizeMake(64, 1, 1)
        encoder.dispatchThreadgroups(gridSize, threadsPerThreadgroup: groupSize)
    }

    private func dispatchBlocks(_ blocks: [BlockInfo], inBuffer: MTLBuffer, outBuffer: MTLBuffer, encoder: MTLComputeCommandEncoder) {
                        if unsortedBlocks.isEmpty { return }""", """                    func dispatchBlocks(_ unsortedBlocks: [SpatialQuantumBlock], inBuffer: MTLBuffer, outBuffer: MTLBuffer, encoder currentEncoder: MTLComputeCommandEncoder) {
                        if unsortedBlocks.isEmpty { return }""")

# Inject clearBuffer properly
clear_code = """
                    func clearBuffer(_ buffer: MTLBuffer, size: Int, encoder currentEncoder: MTLComputeCommandEncoder) {
                        currentEncoder.setComputePipelineState(psoClearBuffer)
                        currentEncoder.setBuffer(buffer, offset: 0, index: 0)
                        let gridSize = MTLSizeMake((size + 63) / 64, 1, 1)
                        let groupSize = MTLSizeMake(64, 1, 1)
                        currentEncoder.dispatchThreadgroups(gridSize, threadsPerThreadgroup: groupSize)
                    }
"""

code = code.replace("                    func dispatchBlocks(_ unsortedBlocks: [SpatialQuantumBlock]", clear_code + "\n                    func dispatchBlocks(_ unsortedBlocks: [SpatialQuantumBlock]")

# Add clearBuffer calls
code = code.replace("dispatchBlocks(qBlocks, inBuffer: normedSpineBuffer, outBuffer: tempQBuffer, encoder: encoder)", "clearBuffer(tempQBuffer, size: 12288, encoder: encoder)\n                            dispatchBlocks(qBlocks, inBuffer: normedSpineBuffer, outBuffer: tempQBuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(kBlocks, inBuffer: normedSpineBuffer, outBuffer: kOutBuffer, encoder: encoder)", "clearBuffer(kOutBuffer, size: 4096, encoder: encoder)\n                            dispatchBlocks(kBlocks, inBuffer: normedSpineBuffer, outBuffer: kOutBuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(vBlocks, inBuffer: normedSpineBuffer, outBuffer: vOutBuffer, encoder: encoder)", "clearBuffer(vOutBuffer, size: 1024, encoder: encoder)\n                            dispatchBlocks(vBlocks, inBuffer: normedSpineBuffer, outBuffer: vOutBuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(linearQkvBlocks, inBuffer: normedSpineBuffer, outBuffer: outQkvBuffer, encoder: encoder)", "clearBuffer(outQkvBuffer, size: 10240, encoder: encoder)\n                            dispatchBlocks(linearQkvBlocks, inBuffer: normedSpineBuffer, outBuffer: outQkvBuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(linearABlocks, inBuffer: normedSpineBuffer, outBuffer: outABuffer, encoder: encoder)", "clearBuffer(outABuffer, size: 64, encoder: encoder)\n                            dispatchBlocks(linearABlocks, inBuffer: normedSpineBuffer, outBuffer: outABuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(linearBBlocks, inBuffer: normedSpineBuffer, outBuffer: outBBuffer, encoder: encoder)", "clearBuffer(outBBuffer, size: 64, encoder: encoder)\n                            dispatchBlocks(linearBBlocks, inBuffer: normedSpineBuffer, outBuffer: outBBuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(linearZBlocks, inBuffer: normedSpineBuffer, outBuffer: outZBuffer, encoder: encoder)", "clearBuffer(outZBuffer, size: 6144, encoder: encoder)\n                            dispatchBlocks(linearZBlocks, inBuffer: normedSpineBuffer, outBuffer: outZBuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(linearOutBlocks, inBuffer: gateOutBuffer, outBuffer: downOutBuffer, encoder: encoder)", "clearBuffer(downOutBuffer, size: 5120, encoder: encoder)\n                            dispatchBlocks(linearOutBlocks, inBuffer: gateOutBuffer, outBuffer: downOutBuffer, encoder: encoder)")

code = code.replace("dispatchBlocks(mlpGateBlocks, inBuffer: normedSpineBuffer, outBuffer: gateOutBuffer, encoder: encoder2)", "clearBuffer(gateOutBuffer, size: 17408, encoder: encoder2)\n                        dispatchBlocks(mlpGateBlocks, inBuffer: normedSpineBuffer, outBuffer: gateOutBuffer, encoder: encoder2)")

code = code.replace("dispatchBlocks(mlpUpBlocks, inBuffer: normedSpineBuffer, outBuffer: upOutBuffer, encoder: encoder2)", "clearBuffer(upOutBuffer, size: 17408, encoder: encoder2)\n                        dispatchBlocks(mlpUpBlocks, inBuffer: normedSpineBuffer, outBuffer: upOutBuffer, encoder: encoder2)")

code = code.replace("dispatchBlocks(mlpDownBlocks, inBuffer: gateOutBuffer, outBuffer: downOutBuffer, encoder: encoder2)", "clearBuffer(downOutBuffer, size: 5120, encoder: encoder2)\n                        dispatchBlocks(mlpDownBlocks, inBuffer: gateOutBuffer, outBuffer: downOutBuffer, encoder: encoder2)")

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(code)
print("Done")
