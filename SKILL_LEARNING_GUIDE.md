# Verantyx Skill Learning System

> **Learning Beyond Information: Operational Skills from Claude Code**

## Overview

Verantyx's Skill Learning System extends learning from just **information** (patterns, responses) to **operational skills** (how to use tools, workflows, code generation). By observing Claude Code's interactions, Verantyx learns not just WHAT was done, but HOW to do it.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│              Cross Structure (6-Axis)                    │
│  ┌──────────┬──────────┬──────────┬──────────┐         │
│  │  FRONT   │    UP    │   RIGHT  │   BACK   │         │
│  │  (Conv)  │ (Inputs) │ (Tools)  │  (Raw)   │         │
│  └──────────┴──────────┴──────────┴──────────┘         │
└─────────────────────────────────────────────────────────┘
                         ↓
              ┌──────────────────────┐
              │   Skill Learner      │
              │  ・Tool Patterns     │
              │  ・Workflows         │
              │  ・Code Templates    │
              │  ・Error Solutions   │
              └──────────────────────┘
                         ↓
              ┌──────────────────────┐
              │   Skill Executor     │
              │  ・File Operations   │
              │  ・Code Generation   │
              │  ・Testing           │
              │  ・Debugging         │
              └──────────────────────┘
                         ↓
              Standalone AI Responses
```

## What Gets Learned

### 1. Tool Patterns

Verantyx observes sequences of tool usage and learns common patterns:

```python
# Example learned pattern:
"Write → Bash → Read"
# Meaning: Create file → Run command → Verify result

# Another pattern:
"Grep → Read → Edit → Bash"
# Meaning: Search → Examine → Modify → Test
```

**Cross Axis**: RIGHT (tool_calls)

**Learning Process**:
1. Extract tool sequences from Cross structure
2. Count frequency of 3+ step sequences
3. Build pattern database with confidence scores

### 2. Workflows

Problem-solving approaches learned from actual conversations:

```python
# Task Type: "creation"
Workflow:
  1. Understand requirements
  2. Design solution
  3. Implement code
  4. Test and verify

# Task Type: "debugging"
Workflow:
  1. Read error message
  2. Identify error location
  3. Apply fix
  4. Re-run tests
```

**Cross Axis**: FRONT (current_conversation)

**Learning Process**:
1. Classify each user request by task type
2. Extract the response workflow
3. Build task type → workflow mappings

### 3. Code Templates

Reusable code patterns extracted from Claude's responses:

```python
# Function template (Python):
def function_name(args):
    """Docstring"""
    # Implementation
    return result

# Class template (Python):
class ClassName:
    def __init__(self):
        pass

    def method(self):
        pass

# Test template:
def test_feature():
    assert condition
```

**Cross Axis**: DOWN (claude_responses)

**Learning Process**:
1. Extract code blocks from responses
2. Classify by type (function, class, test, etc.)
3. Store first 500 chars as reusable template
4. Track language and timestamp

### 4. Error Solutions

Learning how Claude Code solves specific errors:

```python
# Error: ImportError
Solutions learned:
  - "Install missing package with pip"
  - "Check virtual environment activation"
  - "Verify package name spelling"

# Error: SyntaxError
Solutions learned:
  - "Check for missing parentheses"
  - "Verify indentation"
  - "Look for unclosed quotes"
```

**Cross Axis**: BACK (raw_interactions)

**Learning Process**:
1. Detect error messages in interactions
2. Extract error type
3. Store context and solution
4. Build error → solutions database

## How Skills Are Used

### In Standalone Mode

When you run `python3 -m verantyx_cli standalone`, Verantyx uses learned skills:

```python
# User: "Create a Python file called test.py"

# Skill Execution Flow:
1. Task Classification: "creation"
2. Tool Pattern Retrieval: ["Write", "Bash", "Read"]
3. Code Template Retrieval: Python function template
4. Execution (Dry Run):
   - Detect language: Python
   - Get template: def main()...
   - Prepare file creation
   - Return formatted response with steps
```

**Output Example**:
```
[Skill Execution Result]

Request: Create a Python file called test.py

Task Type: creation

Learned Tools Used: Write, Bash, Read

Execution Steps:
   1. detect_language: python
   2. get_template: function
   3. use_learned_template: #!/usr/bin/env python3...
   4. dry_run_complete: /path/to/test.py

Result:
Would create file: /path/to/test.py

Content:
```python
#!/usr/bin/env python3
"""
Description
"""

def main():
    pass

if __name__ == "__main__":
    main()
```

Note: Running in skill execution mode (dry run).
To actually create the file, the content is ready above.

🎓 Skill Learning Active
This response was generated using operational skills learned from Claude Code
```

### Dry Run vs Full Mode

**Standalone Mode (Dry Run)**:
- Analyzes requests
- Shows WHAT would be done
- Demonstrates learned knowledge
- No actual file/system modifications

**Full Mode (python3 -m verantyx_cli chat)**:
- Connects to Claude Code
- Actually executes operations
- Learns NEW skills from execution
- Expands skill database

## Skill Learning Statistics

### Viewing Learned Skills

```bash
# Start standalone mode
python3 -m verantyx_cli standalone

# In chat, type:
skills

# Output:
🎓 Learned Skills Summary

Tool Patterns: 15
Top 5 patterns:
  - Write → Bash → Read: 8 times
  - Grep → Read → Edit: 5 times
  - Read → Edit → Bash: 4 times

Workflows: 23
Distribution:
  - creation: 8
  - debugging: 5
  - search: 4
  - testing: 3
  - modification: 3

Code Templates: 12
Types: function, class, test, main, imports

Error Solutions: 7
Known errors: ImportError, SyntaxError, TypeError, FileNotFoundError, AttributeError
```

## Skill Types and Examples

### File Operations

**Learned Skills**:
- Create file with appropriate template
- Modify existing file (addition, deletion, replacement)
- Verify file exists before operations

**Example**:
```python
# User: "Create config.json"
# Learned response:
1. Detect language: json
2. Use appropriate template
3. Prepare Write tool usage
4. Show dry-run output
```

### Code Generation

**Learned Skills**:
- Language detection from filename
- Template selection (function, class, main)
- Code structure patterns

**Example**:
```python
# User: "Write a function to parse CSV"
# Learned response:
1. Identify: coding task, Python language
2. Template: function
3. Generate structure with learned pattern
```

### Testing

**Learned Skills**:
- Detect test framework (pytest, unittest, npm test, cargo test)
- Construct appropriate test command
- Suggest test workflow

**Example**:
```python
# User: "Run the tests"
# Learned response:
1. Detect project type (Python → pytest)
2. Suggest: pytest
3. Show execution steps
```

### Debugging

**Learned Skills**:
- Extract error type from message
- Retrieve learned solutions
- Suggest debugging workflow

**Example**:
```python
# User: "Fix ImportError: No module named 'requests'"
# Learned response:
1. Identify: ImportError
2. Retrieve solutions: ["pip install requests", "check venv", etc.]
3. Provide step-by-step guidance
```

### Search

**Learned Skills**:
- Extract keywords from request
- Build search patterns
- Suggest appropriate tools (grep vs glob)

**Example**:
```python
# User: "Find all files containing 'config'"
# Learned response:
1. Extract keyword: "config"
2. Pattern: *config*
3. Suggest: grep -r "config" OR find -name "*config*"
```

## Learning Progress

### Learning Levels

| Level | Interactions | Capabilities |
|-------|-------------|--------------|
| **Beginner** | 0-19 | Basic pattern recognition |
| **Intermediate** | 20-49 | Common workflows learned |
| **Advanced** | 50-99 | Diverse skill set |
| **Expert** | 100+ | Comprehensive operational knowledge |

### Improving Skill Learning

**Best Practices**:

1. **Diverse Tasks**: Use various task types (creation, debugging, search, testing, modification)
2. **Multiple Languages**: Python, JavaScript, Rust, Go, etc.
3. **Complex Workflows**: Multi-step tasks teach richer patterns
4. **Error Handling**: Encounter and fix errors to learn solutions
5. **Consistent Use**: Regular interaction builds robust skill database

## Integration with Cross Structure

### How Skills Map to Cross Axes

| Axis | Skill Data | Learning Source |
|------|-----------|-----------------|
| **UP** | User intent patterns | Classification of requests |
| **DOWN** | Code templates | Extracted from Claude responses |
| **RIGHT** | Tool patterns | Sequences of tool usage |
| **LEFT** | Temporal patterns | When skills are used |
| **FRONT** | Workflows | Problem-solving sequences |
| **BACK** | Error solutions | Raw interaction analysis |

### Cross-Referenced Learning

Skills are cross-referenced across axes for richer understanding:

```python
# Example: "Create Python file" request
UP (Input): "create file.py" → Task type: creation
RIGHT (Tools): Write → Bash sequence
DOWN (Output): Python function template
BACK (Raw): Complete interaction context
FRONT (Conv): Full conversation flow

# All combined into skill:
{
  "task_type": "creation",
  "tools": ["Write", "Bash"],
  "template": "python_function",
  "workflow": ["detect_lang", "get_template", "create_file", "verify"]
}
```

## Advanced Features

### Skill Confidence

Each learned skill has a confidence score based on:
- Frequency of observation
- Success rate in past usage
- Consistency across contexts

```python
# High confidence skill (observed 10+ times):
"Write → Bash → Read" (creation): confidence 0.95

# Low confidence skill (observed 1-2 times):
"Glob → Grep → Edit" (search): confidence 0.30
```

### Skill Evolution

Skills evolve as more examples are observed:

```python
# Initial learning (5 interactions):
"creation" → ["Write"]

# After 20 interactions:
"creation" → ["Write", "Bash"]

# After 50 interactions:
"creation" → ["Write", "Bash", "Read"]

# After 100 interactions:
"creation" → ["Read", "Write", "Bash", "Read"]
# (Now includes pre-check and post-verification)
```

### Skill Transfer

Skills learned in one context can transfer to similar contexts:

```python
# Learned from Python:
"Function creation" → Template with def, docstring, return

# Transfers to JavaScript:
"Function creation" → Template with function, comment, return

# Transfers to Rust:
"Function creation" → Template with fn, doc comment, return
```

## Future Enhancements

### Planned Features

1. **Skill Composition**: Combining multiple learned skills for complex tasks
2. **Skill Optimization**: Identifying most efficient tool sequences
3. **Skill Generalization**: Abstracting common patterns across languages
4. **Skill Explanation**: Teaching users about learned techniques
5. **Skill Export/Import**: Sharing skill databases between Verantyx instances

### Long-term Vision

**Self-Improvement Through Skills**:
- Learn new skills from every interaction
- Refine existing skills based on outcomes
- Discover novel skill combinations
- Build comprehensive operational knowledge base

**Autonomous Operation**:
- Execute multi-step tasks independently
- Handle errors using learned solutions
- Adapt workflows to new contexts
- Continuously expand capabilities

## Commands

### Viewing Skills

```bash
# Start standalone mode
python3 -m verantyx_cli standalone

# Inside standalone chat:
skills          # Show learned skills summary
stats           # Show overall learning statistics
train           # Get training recommendations
```

### Testing Skill Learning

```bash
# Test skill learning directly
python3 verantyx_cli/engine/skill_learner.py

# Test skill executor
python3 verantyx_cli/engine/skill_executor.py
```

## Troubleshooting

### "No skills learned yet"

**Cause**: Insufficient interactions in Cross structure

**Solution**:
```bash
# Train with Claude Code first
python3 -m verantyx_cli chat
# Have 10+ diverse conversations
# Then test standalone mode
python3 -m verantyx_cli standalone
```

### "Skill execution failed"

**Cause**: Incomplete skill data

**Solution**: Ensure Cross structure contains:
- User inputs (UP axis)
- Claude responses (DOWN axis)
- Tool calls (RIGHT axis)
- Raw interactions (BACK axis)

### Skills not appearing

**Cause**: Cross file not found or corrupted

**Solution**:
```bash
# Check Cross file exists
ls -lh .verantyx/conversation.cross.json

# Verify JSON is valid
python3 -c "import json; json.load(open('.verantyx/conversation.cross.json'))"
```

## Summary

**Verantyx Skill Learning**:
- ✅ Learns **operational skills**, not just information
- ✅ Extracts **tool patterns, workflows, code templates, error solutions**
- ✅ Uses skills in **standalone mode** (dry run)
- ✅ Continuously **improves** with more interactions
- ✅ **Cross-referenced** across 6 axes for rich understanding

**Key Insight**: Skills are the bridge between **knowing** (information) and **doing** (operation). Verantyx learns both.

---

**Made with 🎓 Skill Learning Architecture**

*Extending AI learning from passive knowledge to active capability*
