import sys

with open('Sources/VerantyxCLI/Stubs.swift', 'r') as f:
    content = f.read()

# Replace the enum entirely
new_enum = """public enum GatekeeperPipelineStep: String, Codable {
    case modelValidation
    case irGeneration
    case vaultSeparation
    case intentTranslate
    case promptBuild
    case llmCall
    case patchParse
    case vaultRehydrate
}"""
import re
content = re.sub(r'public enum GatekeeperPipelineStep: String, Codable \{.*?\}', new_enum, content, flags=re.DOTALL)

with open('Sources/VerantyxCLI/Stubs.swift', 'w') as f:
    f.write(content)
