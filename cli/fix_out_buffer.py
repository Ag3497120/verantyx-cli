with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    text = f.read()

text = text.replace("encoder.setBuffer(outBuffer, offset: 0, index: 0)", "encoder.setBuffer(downOutBuffer, offset: 0, index: 0)")
text = text.replace("dispatchBlocks(oBlocks, inBuffer: qOutBuffer, outBuffer: outBuffer, encoder: encoder)", "dispatchBlocks(oBlocks, inBuffer: qOutBuffer, outBuffer: downOutBuffer, encoder: encoder)")
text = text.replace("encoder.setBuffer(outBuffer, offset: 0, index: 1)", "encoder.setBuffer(downOutBuffer, offset: 0, index: 1)")

with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(text)
