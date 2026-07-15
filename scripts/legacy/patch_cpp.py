with open('/Users/motonishikoudai/verantyx-cli/cli/VRDriver/src/openvr_emulator.cpp', 'r') as f:
    content = f.read()

# Replace SharedFrame
old_shared_frame = """struct SharedFrame {
    uint32_t sequenceNumber;
    uint32_t width;
    uint32_t height;
    uint32_t format;
};"""

new_shared_frame = """struct SharedFrame {
    uint32_t sequenceNumber;
    uint32_t width;
    uint32_t height;
    uint32_t format;
    double renderedTimestamp;
};"""

content = content.replace(old_shared_frame, new_shared_frame)

# Add pHeader->renderedTimestamp = pSharedHands ? pSharedHands->poseTimestamp : 0.0;
old_assign = """                                        pHeader->width = srcWidth * 2;
                                        pHeader->height = srcHeight;
                                        pHeader->format = desc.Format;"""

new_assign = """                                        pHeader->width = srcWidth * 2;
                                        pHeader->height = srcHeight;
                                        pHeader->format = desc.Format;
                                        pHeader->renderedTimestamp = pSharedHands ? pSharedHands->poseTimestamp : 0.0;"""

content = content.replace(old_assign, new_assign)

with open('/Users/motonishikoudai/verantyx-cli/cli/VRDriver/src/openvr_emulator.cpp', 'w') as f:
    f.write(content)
