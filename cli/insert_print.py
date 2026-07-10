with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "let activeUpBlocks = upBlocks.filter" in line:
        new_lines.insert(-1, "                    fputs(\"  > Z=\\(z) Sparsity: \\(activeBlocksCount)/680 (\\(activeBlocksCount * 100 / 680)%)\\n\", stderr)\n")

with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.writelines(new_lines)
