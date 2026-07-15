with open('/Users/motonishikoudai/verantyx-cli/cli/HardwareEncoder.swift', 'r') as f:
    content = f.read()

# Replace processSampleBuffer definition
old_def = """func processSampleBuffer(sampleBuffer: CMSampleBuffer, isKeyFrame: Bool, frameSequence: UInt32) {"""
new_def = """func processSampleBuffer(sampleBuffer: CMSampleBuffer, isKeyFrame: Bool, frameSequence: UInt32, timestamp: Double) {"""
content = content.replace(old_def, new_def)

# Replace the UDPHeader init
old_udp_init = """            var header = UDPHeader(
                magic: UInt32(0x5652414E).littleEndian, // "VRAN"
                frameSequence: frameSequence.littleEndian,
                chunkIndex: UInt32(i).littleEndian,
                totalChunks: UInt32(numFragments).littleEndian,
                chunkOffset: UInt32(chunkOffset).littleEndian,
                payloadSize: UInt32(fragSize).littleEndian
            )"""
new_udp_init = """            var header = UDPHeader(
                magic: UInt32(0x5652414E).littleEndian, // "VRAN"
                frameSequence: frameSequence.littleEndian,
                chunkIndex: UInt32(i).littleEndian,
                totalChunks: UInt32(numFragments).littleEndian,
                chunkOffset: UInt32(chunkOffset).littleEndian,
                payloadSize: UInt32(fragSize).littleEndian,
                timestamp: timestamp
            )"""
content = content.replace(old_udp_init, new_udp_init)

# Replace callback type and extraction
old_cb = """        let frameSequence = sourceFrameRefCon!.assumingMemoryBound(to: UInt32.self).pointee
        
        processSampleBuffer(sampleBuffer: sampleBuffer, isKeyFrame: isKeyFrame, frameSequence: frameSequence)"""
new_cb = """        struct RefConData { var seq: UInt32; var timestamp: Double }
        let refData = sourceFrameRefCon!.assumingMemoryBound(to: RefConData.self).pointee
        
        processSampleBuffer(sampleBuffer: sampleBuffer, isKeyFrame: isKeyFrame, frameSequence: refData.seq, timestamp: refData.timestamp)"""
content = content.replace(old_cb, new_cb)

# Replace caller
old_caller = """                var refConVal = currentSeq
                
                let status = VTCompressionSessionEncodeFrame(compressionSession!,
                                                             imageBuffer: pb,
                                                             presentationTimeStamp: presentationTime,
                                                             duration: CMTime.invalid,
                                                             frameProperties: nil,
                                                             sourceFrameRefcon: &refConVal,"""
new_caller = """                struct RefConData { var seq: UInt32; var timestamp: Double }
                var refConVal = RefConData(seq: currentSeq, timestamp: headerPtr.pointee.renderedTimestamp)
                
                let status = VTCompressionSessionEncodeFrame(compressionSession!,
                                                             imageBuffer: pb,
                                                             presentationTimeStamp: presentationTime,
                                                             duration: CMTime.invalid,
                                                             frameProperties: nil,
                                                             sourceFrameRefcon: &refConVal,"""
content = content.replace(old_caller, new_caller)

with open('/Users/motonishikoudai/verantyx-cli/cli/HardwareEncoder.swift', 'w') as f:
    f.write(content)
