# Verantyx CLI (OpenClaw Fork)

Verantyx is an AI Memory Refresh System built on top of OpenClaw's infrastructure.
OpenClaw provides: Gateway, CLI framework, Auth, Channels, Tools, Sandbox.
Verantyx adds: Spatial Memory, Blind Gatekeeper, Commander Pattern, Thinking Capture.

## Architecture

```
OpenClaw Infrastructure (reused as-is)
├── Gateway (WebSocket + HTTP, token auth)
├── CLI (Commander.js)
├── Channels (Telegram, Discord, Slack, etc.)
├── Auth Profiles (API key rotation, OAuth)
├── Bash Tools (exec, PTY, process management)
├── Sandbox (Docker)
├── Skills system
└── Compaction

Verantyx Layer (src/verantyx/)
├── memory/        — Spatial memory engine (front/near/mid/deep)
├── vfs/           — Blind Gatekeeper (virtual file IDs)
└── agents/        — Commander pattern + thinking capture
    └── system-prompt-wrapper.ts  — Wraps OpenClaw prompts with memory injection
```

## Key Files
- `src/verantyx/memory/engine.ts` — Memory CRUD + front injection
- `src/verantyx/memory/spatial-index.ts` — SPATIAL_INDEX.jcross parser
- `src/verantyx/vfs/gatekeeper.ts` — Virtual File System resolver
- `src/verantyx/agents/orchestrator.ts` — Commander/Worker/Scout dispatch
- `src/verantyx/agents/system-prompt-wrapper.ts` — Memory injection wrapper

## Build
```bash
pnpm install
pnpm build
```
