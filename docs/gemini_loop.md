# Gemini Loop Agent — Implementation Details

## 1. Full Loop Structure — What Happens in 1 Turn

```
Turn 1:

  Mac (gemini_commander.py)
    -> Grid to text + tool description
    -> base64 encode
    -> AppleScript -> Safari JavaScript injection

  Safari Private Window (gemini.google.com)
    -> Gemini receives text
    -> Reasoning (thinking — not capturable)
    -> Response text output to DOM

  Mac (2s polling x N times)
    -> Split by "Gemini の回答" marker
    -> Get latest text
    -> 2 consecutive identical -> stable (complete)
    -> Parse [VERANTYX_CMD] with regex

  Parse result example:
    action: cross_observe
    target: grid

  Mac executes tool
    -> CrossSensor.observe(grid) -> 6-axis analysis
    -> JSON format -> [VERANTYX_RESULT] block
    -> base64 again -> Safari injection -> return result to Gemini

  Duration: ~15-30s/turn
    Breakdown: input injection 1s + initial wait 3s + polling 4-10s
              + tool execution 0.1s + result return cycle
```

```
Turn 2:

  Gemini: Decides next action based on results
    -> [VERANTYX_CMD] action: action_submit target: 2

  Mac: action_submit(2) execution
    -> take_action_fn(2)
    -> HTTP POST to ARC-AGI-3 server
    -> Receive new FrameData
    -> Update current_grid
    -> Return result to Gemini
      {"success": true, "state": "RUNNING",
       "grid_preview": "..."}
```

```
Turns 3-5: Same cycle repeats
```

```
Turn 5: Pure-Through Reset

  Mac -> Gemini: "You will be reset. Write your will."
  Gemini -> Will text (under 200 chars)
  Mac:
    -> Save will to front/will_0.md
    -> safari.close_tab()
    -> 1s wait
    -> safari.open_private() -> new private window
    -> 4s wait (page load)
    -> safari.initialize() -> confirm "OK" response
    -> Send restore prompt (will + current grid + tool description)
    -> turnCount = 0

  New Gemini (completely clean state)
    -> Restore context from will
    -> Continue tool usage
```

```
Game complete or MAX_ACTIONS reached -> end
```

## 2. How Game State is Passed

```
NOT images. Text emoji grid.

Conversion function _grid_to_text():

  Input: [[0,0,1,0],[0,5,0,2],[3,0,0,0]]

  Output:
    Grid: 3x4
    ⬛⬛🔵⬛
    ⬛⬜⬛🔴
    🟢⬛⬛⬛

Color mapping:
  0: ⬛ (black/background)
  1: 🔵 (blue)
  2: 🔴 (red)
  3: 🟢 (green)
  4: 🟡 (yellow)
  5: ⬜ (white/player candidate)
  6: 🟣 (purple)
  7: 🟠 (orange)
  8: 🩵 (light blue)
  9: 🟤 (brown)

Limitations:
  max_rows=10 -> grids over 10 rows are truncated
  "... (50 more rows)" displayed

What Gemini receives:
  "Grid: 64x64 + 10 rows of emoji + truncation notice"
  -> Cannot see full picture of large grids
  -> grid_inspect tool can show partial details

Known issues:
  ❌ Not passed as image -> weak spatial pattern recognition
  ❌ 64x64 grid only shows 10 rows
  ❌ Emoji-based puts load on Gemini's spatial reasoning
```

## 3. Prompt Strategy

### System Prompt (sent on first turn, ~400 tokens)

```
You are a Verantyx agent solving ARC-AGI-3.

## Current Game State
Grid: 64x64
⬛⬛🔵⬛⬛...
(10 rows + truncation)

## Available Tools
[VERANTYX_CMD] format explanation
7 tool list with usage examples

## Rules
1. First analyze grid with cross_observe
2. Find patterns then cross_plan
3. Execute with action_submit
4. Write [DONE] when game is complete
5. Multiple tool requests per turn allowed

Begin analysis.
```

### Restore Prompt (after reset, ~300 tokens)

```
Previous agent was reset.

## Previous Agent's Will
"Maze type game. Player(5) at (2,2).
 Path exists to the right. Color 3 is goal candidate.
 Action 2 (move right) was effective."

## Current Grid
(latest state)

## Tools
Use [VERANTYX_CMD] format for tools.
Continue the task.
```

### What is NOT injected

```
❌ Cross spatial memory front/ (not integrated in ARC version)
❌ session_experience.md (previous agent's experience)
❌ thinking logs (not capturable from free Gemini)
```

## 4. Performance

### Honest Assessment: No games have been run yet.

**Reasons:**
1. ARC-AGI-3 server required (local or API)
2. Test execution needs USE_GEMINI=1 + server running
3. This session only performed unit tests on individual tools

### What Has Been Tested

| Component | Status |
|-----------|--------|
| GeminiCommander._tool_observe() | ✅ Verified on 5x5 test grid |
| GeminiCommander._tool_grid_inspect() | ✅ Partial range display OK |
| GeminiCommander._grid_to_text() | ✅ Emoji conversion OK |
| SafariController (TypeScript) | ✅ Syntactically correct |
| Actual Safari operation | ❌ Not tested |
| Actual Gemini response | ❌ Not tested |
| ARC-AGI-3 game | ❌ Not tested |

### Predicted Performance

```
Per turn:           15-30 seconds (including polling wait)
Per game:           5-20 turns x 25s = 2-8 minutes
25 games:           50 min - 3 hours
Pure-Through resets: 4-5 per game
Subscription warnings: Every 3-5 games (free tier)
```

### Cost

```
Gemini free tier:   $0
Safari operation:   CPU/memory only
ARC-AGI-3 API:      Server dependent
```

### Comparison (v26 Python version track record)

```
v26 standalone: ls20 Level 0 cleared in 23 actions (human baseline: 21) — 83.4% efficiency
Gemini version: Unmeasured, but text-based spatial reasoning expected
                to be inferior to Python's structural inference.
                However, pattern discovery ability may be superior.
```

### Biggest Bottlenecks

```
❌ Grid as text -> weak spatial pattern recognition
❌ 25s per turn -> trial and error takes time
❌ Free tier limits -> hits limit after 3-5 games
```

## 5. File Structure

### TypeScript (verantyx-cli-fork)

```
src/verantyx/audit/
├── safari-controller.ts    (272 lines) — Lowest level Safari automation
├── gemini-bridge.ts        (127 lines) — Session management
├── gemini-agent-loop.ts    (350 lines) — Tool execution loop
├── multi-ai-bridge.ts      (280 lines) — ChatGPT co-usage
├── memory-auditor.ts       (230 lines) — Memory audit
├── operation-auditor.ts    (106 lines) — Operation approval
├── todo-manager.ts         (168 lines) — TODO management
├── audit-service.ts        (78 lines)  — Integration service
└── index.ts                (19 lines)  — Exports
```

### Python (ARC-AGI-3)

```
agents/cross_engine/
└── gemini_commander.py     (450 lines) — ARC-AGI-3 specific Commander
```

## 6. Available Tools

### verantyx-cli-fork (8 tools)

| Tool | Description |
|------|-------------|
| read | Read file (with maxOutputLines limit) |
| write | Write file |
| exec | Shell command (dangerous commands blocked) |
| search | grep search |
| memory_read | Read spatial memory (zone/name) |
| memory_write | Write to spatial memory |
| list | Directory listing |
| gatekeeper | VFS virtual file system (list/search/report) |

### ARC-AGI-3 (7 tools)

| Tool | Description |
|------|-------------|
| cross_observe | 6-axis grid analysis via CrossSensor |
| cross_query | Search discovered rules from AxiomEngine |
| jcross_write | Dynamic rule writing to soul.jcross |
| jcross_simulate | Test jcross code execution |
| cross_plan | Action plan generation (maze/click/toggle/cycle) |
| grid_inspect | Detailed partial grid display with color counts |
| action_submit | Submit action to game server, get next frame |

## 7. vchat Commands

| Command | Function |
|---------|----------|
| `.gemini <task>` | Run task via Gemini with tool access |
| `.chatgpt <task>` | Generate code via ChatGPT (private browser) |
| `.crossval <question>` | Cross-validate with Gemini + ChatGPT |
| `.gemini.stop` | Stop running agent loop |
