import re

with open("Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    code = f.read()

# Find the start of the layer loop
loop_start = "                for z in 0..<numLayers {"
new_loop_start = """                for z in 0..<numLayers {
                    autoreleasepool {"""

code = code.replace(loop_start, new_loop_start)

# Find the end of the layer loop
# It ends right before:
#                 if isVerbose {
#                     let totalInferenceTime = CFAbsoluteTimeGetCurrent() - tInferenceStart
loop_end = """                    commandBuffer.waitUntilCompleted()
                    let t3 = CFAbsoluteTimeGetCurrent()
                    
                    if isVerbose {
                        let totalLayerTime = t3 - t1"""

new_loop_end = """                    commandBuffer.waitUntilCompleted()
                    let t3 = CFAbsoluteTimeGetCurrent()
                    
                    if isVerbose {
                        let totalLayerTime = t3 - t1"""

# Actually, I can just replace the end of the layer loop with `}\n` before `if isVerbose { let totalInferenceTime...`
# Let's find exactly where the `for z` loop ends
