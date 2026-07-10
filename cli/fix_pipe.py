with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    content = f.read()

import re
content = re.sub(
    r"let data = FileHandle\.standardInput\.readData\(ofLength: spineLength\)\n\s+if data\.count < spineLength \{\n\s+break\n\s+\}",
    """var data = Data()
            while data.count < spineLength {
                let chunk = FileHandle.standardInput.readData(ofLength: spineLength - data.count)
                if chunk.isEmpty { break }
                data.append(chunk)
            }
            if data.count < spineLength { break }""",
    content
)

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(content)
