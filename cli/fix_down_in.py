with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    text = f.read()

text = text.replace("dispatchBlocks(activeDownBlocks, inBuffer: upOutBuffer, outBuffer: downOutBuffer, encoder: encoder2)", "dispatchBlocks(activeDownBlocks, inBuffer: gateOutBuffer, outBuffer: downOutBuffer, encoder: encoder2)")

with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(text)
