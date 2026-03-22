# Verantyx CLI

**An AI Memory Refresh System for Continuous Use of Clean Intelligence**

Verantyx CLI is built on top of [OpenClaw](https://github.com/openclaw/openclaw)'s infrastructure, replacing the agent core with a spatial memory system and commander pattern designed to solve AI context pollution.

## The Problem

Modern agentic AI systems suffer from a fundamental problem:

```
Session Start: [Clean context] → [Task 1] → [Task 2] → ... → [Context polluted] → [Hallucination]
```

Long conversations fill the context window with code, tool outputs, and stale information. The AI's judgment degrades as the session progresses. When the session resets, all understanding is lost.

## The Solution: Pure-Through Architecture

Verantyx introduces seven key innovations:

### 1. Spatial Memory (No Deletion, Only Placement)

Inspired by human memory, Verantyx never deletes memories — it places them in spatial zones:

```
front/    → Active context (always injected into prompts)
  ├── session_experience.md   — Previous agent's testimony
  ├── active_context.md       — Current state and tasks
  └── design_decisions.md     — Why decisions were made

near/     → Recently completed work (read when relevant)
mid/      → Established knowledge (project structure reports)
deep/     → Archive (rarely needed)
```

A `SPATIAL_INDEX.jcross` file serves as the map of all memories, using a 6-axis coordinate system (FRONT/NEAR/MID/DEEP/UP/DOWN).

### 2. Commander Pattern (Opus as Experiencer)

The AI is split into roles:

```
┌─────────────────────────────────────────┐
│ Commander (Opus)                         │
│ Role: Experience, judge, decide          │
│ Context: Memories + reports only         │
│ Tools: read/write/edit BLOCKED           │
└──────────┬──────────────────────────────┘
           │
     ┌─────┼──────────────┐
     ↓     ↓              ↓
  Worker  Scout         Worker
  Sonnet  Haiku         Sonnet
  Read    Grep/Build    Edit
  Analyze Check         Modify
```

The Commander never reads code directly. Its 1M context window is reserved for **experience** — understanding user intent, making design decisions, and discovering connections between concepts.

### 3. Blind Gatekeeper (Virtual File System)

Files are referenced by virtual IDs, never by real paths:

```
file_auth_001     → "Unified authentication system"
file_game_eat_001 → "Eating game loop and scoring"
```

The Commander cannot be tempted to read files directly because it doesn't know where they are. All file operations go through worker agents via the Gatekeeper.

### 4. Forced Memory Injection

Every prompt sent to the Commander is automatically prepended with spatial memory context. This is not optional — it's enforced at the architecture level:

```typescript
// system-prompt-wrapper.ts wraps OpenClaw's prompt with Verantyx memory
const prompt = wrapSystemPromptWithVerantyx(openclawPrompt, memory);
// Front memories are ALWAYS injected before any instructions
```

### 5. Automatic Freshness Management

Memory staleness is detected by cross-referencing with git history:

```bash
$ verantyx spatial freshness
  ✅ Fresh    active_context (0d ago)
  ⚠️  3 commits since update    moutheat_structure (2d ago)
  ❌ Stale (12 commits behind)  auth_unification (5d ago)
```

When stale memories are detected, a `freshness_report.md` is automatically placed in `front/` and injected into the next prompt, warning the agent not to trust outdated information.

### 6. Thinking Capture (Extended Thinking API)

The Commander's reasoning process is captured via Anthropic's Extended Thinking API and saved to `front/thinking/`:

```
front/thinking/
  ├── turn_001.md  — "User wants auth refactored. Considering Supabase vs Firebase..."
  ├── turn_002.md  — "The fishing app shares code with the eating app..."
  └── thinking_summary.md  — Rolling summary of last 5 reasoning steps
```

This allows the next agent to inherit not just **what** was done, but **why**.

### 7. Session Experience (Agent Testament)

When a session ends, the Commander writes a personal testimony for the next agent:

```markdown
# Previous Agent's Testimony

I spent 8 hours on this project. Here's what I learned:
- The user values design reasoning over implementation speed
- All projects in this ecosystem are interconnected
- Don't read code directly — sub-agent reports are sufficient
- The auth system uses Supabase, NOT App Groups (we tried and abandoned it)
```

This is not a dry status report — it's an experiential record that the next agent reads as its first action, inheriting the previous agent's understanding and judgment patterns.

## Architecture

```
verantyx-cli/
│
├── OpenClaw Infrastructure (reused as-is)
│   ├── Gateway (WebSocket + HTTP, token auth)
│   ├── CLI Framework (Commander.js, 30+ commands)
│   ├── Auth Profiles (API key rotation, OAuth, multi-provider)
│   ├── Channels (Telegram, Discord, Slack, etc.)
│   ├── Bash Tools (exec, PTY, process management)
│   ├── Sandbox (Docker isolation)
│   ├── Skills System
│   └── Context Compaction
│
├── Verantyx Layer (src/verantyx/)
│   ├── memory/
│   │   ├── engine.ts          — CRUD for spatial memory zones
│   │   ├── spatial-index.ts   — SPATIAL_INDEX.jcross parser/generator
│   │   └── freshness.ts       — Git-based staleness detection
│   ├── vfs/
│   │   └── gatekeeper.ts      — Virtual File System (blind path resolution)
│   └── agents/
│       ├── orchestrator.ts    — Commander/Worker/Scout dispatch + thinking capture
│       └── system-prompt-wrapper.ts  — Forced memory injection into prompts
│
├── Verantyx CLI Commands (src/cli/)
│   ├── verantyx-cli.ts        — `spatial` and `vfs` commands
│   └── verantyx-chat.ts       — `vchat` with agent labels and streaming
│
├── Modified OpenClaw Files
│   ├── src/agents/pi-embedded-runner/system-prompt.ts  — Memory injection hook
│   ├── src/agents/openclaw-tools.ts  — Commander tool blocking
│   └── src/cli/program/command-registry.ts  — Verantyx command registration
│
└── verantyx-start.sh          — Unified launcher script
```

## Quick Start

```bash
# Clone
git clone https://github.com/motonishikoudai/verantyx-cli.git
cd verantyx-cli

# Install
pnpm install

# Build
pnpm build

# Initial setup (API keys, model selection)
./verantyx-start.sh setup

# Start chatting
./verantyx-start.sh chat
```

## Commands

### Unified Launcher

```bash
./verantyx-start.sh setup       # Initial setup (API keys + env)
./verantyx-start.sh start       # Start gateway + freshness check
./verantyx-start.sh stop        # Stop gateway
./verantyx-start.sh chat        # Commander chat with tool labels
./verantyx-start.sh status      # Show status + freshness
./verantyx-start.sh memory      # List spatial memories
./verantyx-start.sh inject      # Preview memory injection
./verantyx-start.sh vfs         # List virtual files
./verantyx-start.sh freshness   # Check memory freshness vs git
```

### Direct CLI Commands

```bash
# Spatial Memory
node openclaw.mjs spatial list                    # List all memories by zone
node openclaw.mjs spatial read <name>             # Read a specific memory
node openclaw.mjs spatial write <zone> <name>     # Write a memory
node openclaw.mjs spatial move <name> <zone>      # Move between zones
node openclaw.mjs spatial index                   # Show SPATIAL_INDEX.jcross
node openclaw.mjs spatial freshness               # Check staleness
node openclaw.mjs spatial inject                  # Preview injection content

# Virtual File System (Blind Gatekeeper)
node openclaw.mjs vfs list                        # List all virtual files
node openclaw.mjs vfs list --category auth        # Filter by category
node openclaw.mjs vfs report file_auth_001        # Structure report
node openclaw.mjs vfs search "deleteAccount"      # Search by pattern

# Commander Chat
node openclaw.mjs vchat                           # Interactive chat
node openclaw.mjs vchat --no-thinking             # Hide thinking display

# All OpenClaw commands also work
node openclaw.mjs agent --message "..."           # One-shot agent
node openclaw.mjs configure --section model       # Model setup
node openclaw.mjs gateway run                     # Start gateway
```

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...          # Anthropic API key

# Verantyx-specific
VERANTYX_MEMORY_ROOT=/path/to/memory  # Spatial memory directory
VERANTYX_VFS_MAPPING=/path/to/vfs.json # VFS mapping file
VERANTYX_COMMANDER_MODE=true          # Block read/write/edit for commander
VERANTYX_PROJECT_ROOT=/path/to/project # Project root for git freshness

# Optional providers
GEMINI_API_KEY=...                    # Google Gemini
OPENAI_API_KEY=sk-...                 # OpenAI
OPENROUTER_API_KEY=sk-or-...          # OpenRouter
```

## Research Background

Verantyx is a continuation of the ILM (Incremental Learning Memory) research project, exploring how to eliminate context pollution in agentic AI systems.

### Key Research Questions

1. **Can spatial memory replace conversation history?** — Instead of re-reading the entire chat, inject only relevant memories (~500 tokens vs ~20,000 tokens)
2. **Does the Commander pattern improve judgment quality?** — By reserving the context window for "experience" rather than "work"
3. **Can agent testimonies transfer understanding?** — Not just facts, but judgment patterns and reasoning approaches
4. **Does blindness improve decision-making?** — When the Commander can't see file paths, it can't be tempted to read directly

### Preliminary Results

In testing with a fresh Sonnet agent reading only the spatial memory:
- **82% project understanding recovery** from 4 memory files
- **Zero real file paths leaked** through the Blind Gatekeeper
- **6/7 questions answered correctly** about project architecture

## License

PolyForm Noncommercial License 1.0.0

Permitted: Personal research, academic research, educational purposes.
Prohibited: Commercial use, business use, selling services built on this system.

## Acknowledgments

- [OpenClaw](https://github.com/openclaw/openclaw) — Gateway, CLI, auth, channels, tools infrastructure
- ILM (Incremental Learning Memory) — Initial experiments in memory refresh
- DNA Double Helix Structure — Design philosophy for agent relay

---

*"AI agents may die, but knowledge flows through."*
