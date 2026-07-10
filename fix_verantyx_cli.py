import re

with open('/Users/motonishikoudai/verantyx-cli/cli/VRDriver/src/openvr_emulator.cpp', 'r') as f:
    content = f.read()

# Replace return types to void
content = re.sub(r'virtual\s+vr::[A-Za-z0-9_]+_t\*\s+([A-Za-z0-9_]+)\(', r'virtual void \1(', content)
content = re.sub(r'virtual\s+[A-Za-z0-9_]+_t\*\s+([A-Za-z0-9_]+)\(', r'virtual void \1(', content)

# Remove 'return pRet;'
content = re.sub(r'return pRet;', r'return;', content)

# Fix typo
content = content.replace('if (pSharedHeader)', 'if (pSharedHands)')
content = content.replace('pSharedHeader->sequenceNumber++', 'pSharedHands->sequenceNumber++')

with open('/Users/motonishikoudai/verantyx-cli/cli/VRDriver/src/openvr_emulator.cpp', 'w') as f:
    f.write(content)
