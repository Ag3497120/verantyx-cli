import re

files_to_patch = [
    'Sources/Verantyx/Gatekeeper/JCrossVault.swift',
    'Sources/Verantyx/Engine/JCrossSchemaGenerator.swift',
    'Sources/Verantyx/Engine/OllamaNEREngine.swift',
    'Sources/Verantyx/Engine/TranspilationPipeline.swift'
]

# We will use #if CLI ... #else ... #endif
for file in files_to_patch:
    try:
        with open(file, 'r') as f:
            content = f.read()
            
        content = content.replace("GatekeeperConfig.shared.useOllamaNER", "GatekeeperModeState.shared.useOllamaNER")
        content = content.replace("GatekeeperConfig.shared.commanderModel", "GatekeeperModeState.shared.commanderModel")
        content = content.replace("(GatekeeperConfig.shared.vault!)", "GatekeeperModeState.shared.vault")
        
        with open(file, 'w') as f:
            f.write(content)
        print(f"Reverted {file}")
    except Exception as e:
        pass

