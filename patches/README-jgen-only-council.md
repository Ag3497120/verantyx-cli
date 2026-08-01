# JGEN-only vector-bus (apply on Verantyx IDE)

Cloud agent **cannot push to `Ag3497120/Verantyx`** (403 for cursor[bot]).
This directory is the complete change set to apply on that repo.

## Goal

Use **only JGEN** for council + execution:

- No Layer-3 Ollama escalation
- L2 does **not** go through `AgentLoop` (stops `[MEM:check_rollback]` collapse)
- Eternal memory recall + soft-token steer stay on the JGEN vector bus
- Template: **JGENベクトルバス（エスカレなし）** (`jgen-vector-bus`)

## Apply (preferred: patch)

```bash
cd /path/to/Verantyx
git checkout -b cursor/jgen-only-council-64b8
git am path/to/verantyx-cli/patches/jgen-only-council-64b8.patch
# if am fails:
#   git apply path/to/verantyx-cli/patches/jgen-only-council-64b8.patch
git push -u origin cursor/jgen-only-council-64b8
```

## Apply (copy files)

Mirror of the touched files (relative to `cli/VerantyxIDE/`):

```
patches/jgen-only-council/
  Sources/Verantyx/Engine/JGenSpeakAgent.swift          (new)
  Sources/Verantyx/Engine/LayeredRunOrchestrator.swift
  Sources/Verantyx/Engine/CouncilOrchestrator.swift
  Sources/Verantyx/Engine/ArchitectureTemplate.swift
  Sources/Verantyx/Engine/SoftSequence.swift
  Sources/Verantyx/Engine/TemplateSetupPlanner.swift
  Sources/Verantyx/AppState.swift
  Sources/Verantyx/Views/ModelSelectorBarView.swift
  Verantyx.xcodeproj/project.pbxproj
```

Copy over `cli/VerantyxIDE/` in Verantyx, then build.

## Use in IDE

1. Load a `.jgen` (Settings → JGEN)
2. JGEN options → Architecture template → **JGENベクトルバス（エスカレなし）** → approve
3. Turn on **通常のチャットでも合議を使う**
4. Chat — L2 log should say `JGEN native` / `JGenSpeakAgent`, not Nano AgentLoop

## Local Verantyx commit

Built and committed locally as `4788c46c` on branch `cursor/jgen-only-council-64b8` (push denied).
