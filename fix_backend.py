import re

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    content = f.read()

# Replace blockInfos creation
content = re.sub(
    r"var blockInfos: \[BlockInfo\] = \[\]\n.*?for block in blocks \{.*?if block\.matrixType == 0 \|\| block\.matrixType == 1 \{ continue \}\n.*?let info = BlockInfo.*?blockInfos\.append\(info\)\n.*?}",
    """var blockInfos: [BlockInfo] = []
                            blockInfos.reserveCapacity(blocks.count)
                            for block in blocks {
                                if block.matrixType == 0 || block.matrixType == 1 { continue }
                                let info = BlockInfo(rowIdx: UInt32(block.rowIdx), colIdx: UInt32(block.colIdx), blockSize: UInt32(64), pad: 0, byteOffset: UInt64(block.fileOffset))
                                blockInfos.append(info)
                            }""",
    content,
    flags=re.DOTALL
)

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(content)
