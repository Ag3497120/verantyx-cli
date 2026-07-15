with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    content = f.read()

content = content.replace(
    "guard let blocks = runtime.spatialGraph[z], !blocks.isEmpty else { continue }",
    "guard let blocks = runtime.spatialGraph[z], !blocks.isEmpty else { continue }\n                    print(\"  > Executing Z=\\(z)\")\n                    fflush(stdout)"
)

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(content)
