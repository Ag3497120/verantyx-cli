import yaml

with open('project.yml', 'r') as f:
    data = yaml.safe_load(f)

# Filter out TranspilationPipeline.swift
sources = data['targets']['verantyx-cli']['sources']
sources = [s for s in sources if 'TranspilationPipeline.swift' not in s['path']]
data['targets']['verantyx-cli']['sources'] = sources

with open('project.yml', 'w') as f:
    yaml.dump(data, f, sort_keys=False)
