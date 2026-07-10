import re

with open("Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    code = f.read()

def replace_with_print(match):
    return f'if isVerbose && z == 3 {{ fputs("  > About to encode {match.group(1)}\\n", stderr); fflush(stderr) }}\n' + match.group(0)

# We want to add print statements before each pipeline state encoding in the Attention block
code = re.sub(r'(\s*)(encoder\.setComputePipelineState\(psoRope\))', r'\1if isVerbose && z == 3 { fputs("  > About to encode psoRope\\n", stderr); fflush(stderr) }\n\1\2', code)
code = re.sub(r'(\s*)(encoder\.setComputePipelineState\(psoWriteKVCache\))', r'\1if isVerbose && z == 3 { fputs("  > About to encode psoWriteKVCache\\n", stderr); fflush(stderr) }\n\1\2', code)
code = re.sub(r'(\s*)(encoder\.setComputePipelineState\(psoAttention\))', r'\1if isVerbose && z == 3 { fputs("  > About to encode psoAttention\\n", stderr); fflush(stderr) }\n\1\2', code)

# We also want to remove psoSiluMul block from Attention route
# It looks like:
# encoder.setComputePipelineState(psoSiluMul)
# encoder.setBuffer(qOutBuffer, offset: 0, index: 0)
# encoder.setBuffer(qGateBuffer, offset: 0, index: 1)
# encoder.dispatchThreadgroups(...)
target_silu = re.compile(r'(\s*)encoder\.setComputePipelineState\(psoSiluMul\)\s*encoder\.setBuffer\(qOutBuffer, offset: 0, index: 0\)\s*encoder\.setBuffer\(qGateBuffer, offset: 0, index: 1\)\s*encoder\.dispatchThreadgroups\([^\)]+\)', re.MULTILINE)
code = target_silu.sub(r'\1// REMOVED psoSiluMul for Attention', code)

# And before oBlocks dispatch
code = re.sub(r'(\s*)(encoder\.setComputePipelineState\(psoBlockMatMul\)\s*dispatchBlocks\(oBlocks,)', r'\1if isVerbose && z == 3 { fputs("  > About to encode psoBlockMatMul oBlocks\\n", stderr); fflush(stderr) }\n\1\2', code)

with open("Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(code)

