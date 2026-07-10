import re

files_to_patch = [
    'Sources/Verantyx/Gatekeeper/JCrossVault.swift',
    'Sources/Verantyx/Engine/JCrossSchemaGenerator.swift',
    'Sources/Verantyx/Engine/TranspilationPipeline.swift',
    'Sources/Verantyx/Engine/OllamaNEREngine.swift'
]

# We will replace `GatekeeperModeState.shared.useOllamaNER` with `GatekeeperConfig.shared.useOllamaNER`
# and `GatekeeperModeState.shared.commanderModel` with `GatekeeperConfig.shared.commanderModel`
# and `GatekeeperModeState.shared.vault` with `GatekeeperConfig.shared.vault!`

for file in files_to_patch:
    try:
        with open(file, 'r') as f:
            content = f.read()
            
        content = content.replace("GatekeeperModeState.shared.useOllamaNER", "GatekeeperConfig.shared.useOllamaNER")
        content = content.replace("GatekeeperModeState.shared.commanderModel", "GatekeeperConfig.shared.commanderModel")
        content = content.replace("GatekeeperModeState.shared.vault", "(GatekeeperConfig.shared.vault!)")
        
        with open(file, 'w') as f:
            f.write(content)
        print(f"Patched {file}")
    except FileNotFoundError:
        print(f"Skipped {file}")

