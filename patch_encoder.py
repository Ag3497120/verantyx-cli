with open('/Users/motonishikoudai/verantyx-cli/cli/HardwareEncoder.swift', 'r') as f:
    content = f.read()

# Replace SharedFrame
old_shared_frame = """struct SharedFrame {
    var sequenceNumber: UInt32
    var width: UInt32
    var height: UInt32
    var format: UInt32
}"""

new_shared_frame = """struct SharedFrame {
    var sequenceNumber: UInt32
    var width: UInt32
    var height: UInt32
    var format: UInt32
    var renderedTimestamp: Double
}"""

content = content.replace(old_shared_frame, new_shared_frame)

# Replace UDPHeader
old_udp_header = """struct UDPHeader {
    var magic: UInt32 // 0x5652414E ("VRAN")
    var frameSequence: UInt32
    var chunkIndex: UInt32
    var totalChunks: UInt32
    var chunkOffset: UInt32
    var payloadSize: UInt32
}"""

new_udp_header = """struct UDPHeader {
    var magic: UInt32 // 0x5652414E ("VRAN")
    var frameSequence: UInt32
    var chunkIndex: UInt32
    var totalChunks: UInt32
    var chunkOffset: UInt32
    var payloadSize: UInt32
    var timestamp: Double
}"""

content = content.replace(old_udp_header, new_udp_header)

with open('/Users/motonishikoudai/verantyx-cli/cli/HardwareEncoder.swift', 'w') as f:
    f.write(content)
