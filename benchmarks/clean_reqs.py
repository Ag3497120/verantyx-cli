import os

def clean_requirements(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Skip conda-specific lines (starting with _)
        if line.startswith('_'):
            continue
            
        # Handle conda-style dependencies (name=version=build)
        # or (name=version)
        if '=' in line:
            parts = line.split('=')
            name = parts[0]
            if len(parts) > 1:
                version = parts[1]
                # Filter out obvious conda names or paths
                if '/' in version or name in ['python', 'pip', 'setuptools', 'wheel']:
                    continue
                # Simple heuristic: if it looks like a version, keep it
                cleaned.append(f"{name}=={version}")
            else:
                cleaned.append(name)
        else:
            cleaned.append(line)
            
    with open(file_path + '.pip', 'w') as f:
        f.write('\n'.join(cleaned))
    print(f"Created {file_path}.pip")

# Clean all requirements
clean_requirements('/Users/motonishikoudai/verantyx-cli/benchmarks/locomo/requirements.txt')
clean_requirements('/Users/motonishikoudai/verantyx-cli/benchmarks/LLMTest_NeedleInAHaystack/requirements.txt')
clean_requirements('/Users/motonishikoudai/verantyx-cli/benchmarks/babilong/requirements.txt')
