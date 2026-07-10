with open('/Users/motonishikoudai/verantyx-cli/cli/VRDriver/src/openvr_emulator.cpp', 'r') as f:
    content = f.read()

content = content.replace('pSharedHands->sequenceNumber++;', '//pSharedHands->sequenceNumber++;')

with open('/Users/motonishikoudai/verantyx-cli/cli/VRDriver/src/openvr_emulator.cpp', 'w') as f:
    f.write(content)
