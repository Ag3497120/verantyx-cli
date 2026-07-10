with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    text = f.read()

import re

# Replace print() with fputs(..., stderr)
text = re.sub(r'print\("([^"]+)"\)', r'fputs("\1\\n", stderr); fflush(stderr)', text)
text = text.replace(r'\n\n', r'\n')

with open("/Users/motonishikoudai/verantyx-cli/cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(text)
