# 📚 .jcross Language — Complete Guide

> **The Language Where Code, Data, and Logic Coexist**

---

## 📖 Table of Contents

1. [Introduction: What is .jcross?](#1-introduction-what-is-jcross)
2. [Core Philosophy](#2-core-philosophy)
3. [The 6-Axis Cross Structure](#3-the-6-axis-cross-structure)
4. [Syntax Fundamentals](#4-syntax-fundamentals)
5. [Data Types & Variables](#5-data-types--variables)
6. [Control Flow & Patterns](#6-control-flow--patterns)
7. [Functions & Procedures](#7-functions--procedures)
8. [Using .jcross as Data Storage](#8-using-jcross-as-data-storage)
9. [Real-World Examples](#9-real-world-examples)
10. [Best Practices](#10-best-practices)
11. [Advanced Techniques](#11-advanced-techniques)

---

## 1. Introduction: What is .jcross?

**.jcross** (pronounced "jay-cross") is a revolutionary programming language developed as part of the Verantyx project. Unlike traditional languages that separate code from data, .jcross **unifies** them into a single, coherent structure.

### 🎯 Key Insight

> **In .jcross, your data IS your code, and your code IS your data.**

This fundamental principle eliminates the traditional separation between:
- **Source code** (`.py`, `.js`, `.java`)
- **Data files** (`.json`, `.xml`, `.yaml`)
- **Configuration** (`.ini`, `.toml`, `.env`)

In .jcross, **all three live in the same file**, organized along six spatial axes.

### Why .jcross?

Traditional programming languages force you to think in **linear sequences**:
```python
# Traditional Python
def process(data):
    result = step1(data)
    result = step2(result)
    result = step3(result)
    return result
```

.jcross lets you think in **multi-dimensional structures**:
```jcross
CROSS processor {
    AXIS UP {
        goal: "Transform input data"
    }
    AXIS DOWN {
        steps: [step1, step2, step3]
    }
    AXIS FRONT {
        current_data: {}
    }
    FUNCTION process(input) {
        FRONT.current_data = input
        FOR step IN DOWN.steps {
            FRONT.current_data = step(FRONT.current_data)
        }
        RETURN FRONT.current_data
    }
}
```

---

## 2. Core Philosophy

### 2.1 Three Pillars

.jcross is built on three foundational principles:

#### Pillar 1: **Structure Before Logic**
Traditional languages: Write functions first, organize later.
.jcross: Define your Cross structure first, then populate it with logic.

#### Pillar 2: **Spatial Reasoning**
Traditional languages: Think in terms of time (before/after, caller/callee).
.jcross: Think in terms of space (up/down, front/back, left/right).

#### Pillar 3: **Code as Data, Data as Code**
Traditional languages: Separate `.py` files from `.json` files.
.jcross: One `.jcross` file contains both executable logic and stored data.

### 2.2 The Cross Structure Metaphor

Imagine you're organizing information about a **tree**:

| Axis | Direction | What It Represents |
|------|-----------|-------------------|
| **UP** | ↑ | The tree's purpose (provide oxygen, shade) |
| **DOWN** | ↓ | The tree's foundation (roots, soil composition) |
| **LEFT** | ← | The tree's history (age, growth rings) |
| **RIGHT** | → | The tree's future (growth potential, offspring) |
| **FRONT** | ⊙ | What's visible now (leaves, branches) |
| **BACK** | ⊗ | What's hidden (internal structure, nutrients) |

This same 6-axis framework applies to **any domain** — conversations, images, user behavior, machine learning models.

### 2.3 Why Six Axes?

Six axes provide a **complete spatial model** of information:
- **Vertical** (UP/DOWN): Goals vs. Foundations
- **Horizontal** (LEFT/RIGHT): Past vs. Future
- **Depth** (FRONT/BACK): Visible vs. Hidden

This mirrors how humans naturally organize knowledge in 3D space.

---

## 3. The 6-Axis Cross Structure

Every `.jcross` file contains one or more **CROSS** structures. Here's the full axis specification:

| Axis | Direction | Meaning | Typical Use |
|------|-----------|---------|-------------|
| `UP` | ↑ Upward | **Input / Questions** | User inputs, queries, requests |
| `DOWN` | ↓ Downward | **Output / Answers** | AI responses, results, conclusions |
| `LEFT` | ← Leftward | **Temporal / Past** | Timestamps, history, logs |
| `RIGHT` | → Rightward | **Actions / Future** | Commands executed, next steps |
| `FRONT` | ⊙ Forward | **Active Context** | Current conversation, focus |
| `BACK` | ⊗ Backward | **Metadata / Background** | System info, configurations |

### 3.1 Anatomy of a CROSS

```jcross
CROSS conversation_memory {
    // UP: User's perspective
    AXIS UP {
        user_inputs: []
        total_questions: 0
    }

    // DOWN: AI's perspective
    AXIS DOWN {
        ai_responses: []
        total_answers: 0
    }

    // LEFT: Historical data
    AXIS LEFT {
        timestamps: []
        session_history: []
    }

    // RIGHT: Actions taken
    AXIS RIGHT {
        tools_used: []
        files_modified: []
    }

    // FRONT: Current state
    AXIS FRONT {
        active_thread: null
        current_topic: ""
    }

    // BACK: Metadata
    AXIS BACK {
        session_id: ""
        user_profile: {}
    }
}
```

### 3.2 Why This Structure?

This structure is **self-documenting**:
- Looking at `UP` tells you what the user wants
- Looking at `DOWN` tells you what the AI provided
- Looking at `LEFT` shows the conversation timeline
- Looking at `RIGHT` shows what actions were taken
- Looking at `FRONT` shows the current focus
- Looking at `BACK` shows system metadata

No comments needed — the structure itself explains the data.

---

## 4. Syntax Fundamentals

### 4.1 Keywords

.jcross has 5 primary keywords:

| Keyword | Purpose | Example |
|---------|---------|---------|
| `CROSS` | Define a Cross structure | `CROSS my_system { ... }` |
| `AXIS` | Define one of 6 axes | `AXIS UP { ... }` |
| `FUNCTION` | Define executable logic | `FUNCTION process(x) { ... }` |
| `PATTERN` | Define pattern matching | `PATTERN detect(text) { ... }` |
| `MATCH` | Pattern matching block | `MATCH x { ... }` |

### 4.2 Comments

```jcross
// Single-line comment

/*
   Multi-line
   comment
*/

"""
Documentation string
(used for file/module docs)
"""
```

### 4.3 Basic Structure

```jcross
"""
File description here
"""

CROSS structure_name {
    AXIS UP {
        field1: value1
        field2: value2
    }

    AXIS DOWN {
        field3: value3
    }

    FUNCTION my_function(param1, param2) {
        // Logic here
        RETURN result
    }
}
```

### 4.4 Accessing Cross Data

```jcross
CROSS example {
    AXIS UP {
        counter: 0
        items: []
    }

    FUNCTION increment() {
        // Access axis fields with dot notation
        UP.counter = UP.counter + 1
        RETURN UP.counter
    }

    FUNCTION add_item(item) {
        UP.items.APPEND(item)
        RETURN LENGTH(UP.items)
    }
}
```

**Key Rule**: Inside a `CROSS`, you can access any axis field using `AXIS_NAME.field_name`.

---

## 5. Data Types & Variables

### 5.1 Primitive Types

```jcross
AXIS UP {
    // Numbers
    integer_value: 42
    float_value: 3.14

    // Strings
    name: "Verantyx"
    description: "AI system"

    // Booleans
    is_active: true
    is_complete: false

    // Null
    optional_field: null
}
```

### 5.2 Collections

```jcross
AXIS UP {
    // Lists (arrays)
    numbers: [1, 2, 3, 4, 5]
    names: ["Alice", "Bob", "Carol"]
    mixed: [1, "two", 3.0, true]

    // Objects (dictionaries)
    user: {
        name: "John",
        age: 30,
        active: true
    }

    // Nested structures
    data: {
        items: [
            { id: 1, name: "First" },
            { id: 2, name: "Second" }
        ],
        metadata: {
            created: "2026-03-12",
            version: 1
        }
    }
}
```

### 5.3 Variables in Functions

```jcross
FUNCTION calculate(x, y) {
    // Local variables
    sum = x + y
    product = x * y
    average = sum / 2

    // Storing in axis
    DOWN.last_result = {
        sum: sum,
        product: product,
        average: average
    }

    RETURN average
}
```

### 5.4 Built-in Functions

```jcross
FUNCTION example() {
    // String operations
    text = "hello world"
    upper = UPPER(text)           // "HELLO WORLD"
    lower = LOWER(text)           // "hello world"
    len = LENGTH(text)            // 11

    // Array operations
    items = [1, 2, 3, 4, 5]
    items.APPEND(6)               // [1, 2, 3, 4, 5, 6]
    items.REMOVE(3)               // [1, 2, 4, 5, 6]
    first = items[0]              // 1

    // Time operations
    now = NOW()                   // Current timestamp

    // Type checking
    is_str = IS_STRING(text)      // true
    is_num = IS_NUMBER(42)        // true

    RETURN {
        upper: upper,
        length: len,
        items: items,
        timestamp: now
    }
}
```

---

## 6. Control Flow & Patterns

### 6.1 Conditionals

```jcross
FUNCTION check_value(x) {
    IF x > 10 {
        RETURN "large"
    }
    ELSE IF x > 5 {
        RETURN "medium"
    }
    ELSE {
        RETURN "small"
    }
}
```

### 6.2 Loops

```jcross
FUNCTION process_items(items) {
    results = []

    // For loop
    FOR item IN items {
        processed = item * 2
        results.APPEND(processed)
    }

    RETURN results
}

FUNCTION count_to(n) {
    counter = 0

    // While loop
    WHILE counter < n {
        counter = counter + 1
    }

    RETURN counter
}
```

### 6.3 Pattern Matching

Pattern matching is a powerful feature in .jcross:

```jcross
PATTERN detect_structure_type(text) {
    MATCH text {
        CONTAINS ["とは", "とはなにか", "とは何か"] -> "definition"
        CONTAINS ["方法", "やり方", "手順"] -> "how_to"
        CONTAINS ["理由", "なぜ", "why"] -> "explanation"
        CONTAINS ["いつ", "when", "時期"] -> "temporal"
        DEFAULT -> "general"
    }
}
```

### 6.4 Pattern Syntax

```jcross
PATTERN classify(input) {
    MATCH input {
        // Exact match
        "hello" -> "greeting"

        // Contains match
        CONTAINS "error" -> "error_message"

        // Multiple conditions
        CONTAINS ["bug", "issue", "problem"] -> "bug_report"

        // Starts with
        STARTS_WITH "http" -> "url"

        // Ends with
        ENDS_WITH ".jpg" -> "image"

        // Regex pattern (advanced)
        REGEX "^[0-9]+$" -> "numeric"

        // Default case
        DEFAULT -> "unknown"
    }
}
```

### 6.5 Conditional Patterns

```jcross
FUNCTION calculate_score(pieces) {
    total = 0

    // Pattern matching on structure
    MATCH pieces {
        HAS "subject" AND HAS "explanation" -> {
            total = total + 40
        }
        HAS "examples" -> {
            total = total + 20
        }
        DEFAULT -> {
            total = 10
        }
    }

    RETURN total
}
```

---

## 7. Functions & Procedures

### 7.1 Basic Functions

```jcross
CROSS calculator {
    AXIS DOWN {
        last_result: 0
    }

    FUNCTION add(a, b) {
        result = a + b
        DOWN.last_result = result
        RETURN result
    }

    FUNCTION multiply(a, b) {
        result = a * b
        DOWN.last_result = result
        RETURN result
    }
}
```

### 7.2 Functions with Side Effects

```jcross
CROSS todo_list {
    AXIS UP {
        tasks: []
    }

    AXIS DOWN {
        completed: []
    }

    FUNCTION add_task(task) {
        UP.tasks.APPEND({
            id: LENGTH(UP.tasks) + 1,
            description: task,
            created: NOW()
        })
        RETURN LENGTH(UP.tasks)
    }

    FUNCTION complete_task(task_id) {
        // Find and remove from tasks
        FOR i, task IN UP.tasks {
            IF task.id == task_id {
                DOWN.completed.APPEND(task)
                UP.tasks.REMOVE(i)
                RETURN true
            }
        }
        RETURN false
    }
}
```

### 7.3 Helper Functions

```jcross
FUNCTION calculate_score(pieces) {
    score = 0

    // Call helper functions
    score = score + check_required_pieces(pieces)
    score = score + check_optional_pieces(pieces)

    RETURN score / 100.0
}

FUNCTION check_required_pieces(pieces) {
    points = 0
    required = ["subject", "explanation"]

    FOR piece IN required {
        IF piece IN pieces {
            points = points + 40
        }
    }

    RETURN points
}

FUNCTION check_optional_pieces(pieces) {
    points = 0
    optional = ["examples", "details"]

    FOR piece IN optional {
        IF piece IN pieces {
            points = points + 10
        }
    }

    RETURN points
}
```

### 7.4 Recursive Functions

```jcross
FUNCTION factorial(n) {
    IF n <= 1 {
        RETURN 1
    }
    RETURN n * factorial(n - 1)
}

FUNCTION fibonacci(n) {
    IF n <= 1 {
        RETURN n
    }
    RETURN fibonacci(n - 1) + fibonacci(n - 2)
}
```

---

## 8. Using .jcross as Data Storage

One of .jcross's most powerful features: **the file itself is the database**.

### 8.1 Traditional Approach (Separate Files)

```
# Old way - separate files
program.py          # Code
database.json       # Data
config.yaml         # Settings
```

### 8.2 .jcross Approach (Unified)

```jcross
"""
Conversation Memory Storage
This .jcross file contains both the data and the logic to manipulate it.
"""

CROSS conversation_memory {
    // DATA: Stored directly in the .jcross file
    AXIS UP {
        user_inputs: [
            "[CTX:ctx_0_1773270661|TOPIC:apple] apple",
            "[CTX:ctx_1_1773270702|TOPIC:AI] How does AI work?"
        ]
        total_messages: 2
    }

    AXIS DOWN {
        claude_responses: [
            "An apple is a fruit...",
            "AI works by processing data..."
        ]
    }

    AXIS LEFT {
        timestamps: [
            "2026-03-12T08:11:01.763605",
            "2026-03-12T08:12:22.145293"
        ]
    }

    // LOGIC: Functions to manipulate the data
    FUNCTION log_user_input(user_input) {
        timestamp = NOW()
        UP.user_inputs.APPEND(user_input)
        UP.total_messages = UP.total_messages + 1
        LEFT.timestamps.APPEND(timestamp)

        // Auto-save to disk
        SELF.save()

        RETURN {
            total_inputs: UP.total_messages,
            total_responses: LENGTH(DOWN.claude_responses)
        }
    }

    FUNCTION log_claude_response(response) {
        timestamp = NOW()
        DOWN.claude_responses.APPEND(response)
        LEFT.timestamps.APPEND(timestamp)

        // Auto-save to disk
        SELF.save()

        RETURN LENGTH(DOWN.claude_responses)
    }

    FUNCTION get_conversation_history() {
        history = []

        FOR i IN RANGE(LENGTH(UP.user_inputs)) {
            history.APPEND({
                timestamp: LEFT.timestamps[i * 2],
                user: UP.user_inputs[i],
                ai: DOWN.claude_responses[i]
            })
        }

        RETURN history
    }
}
```

### 8.3 How It Works

1. **Initial State**: File contains empty arrays
2. **User Input**: Call `log_user_input("Hello")` → data appended → file auto-saved
3. **AI Response**: Call `log_claude_response("Hi!")` → data appended → file auto-saved
4. **Query**: Call `get_conversation_history()` → returns structured data

**The file updates itself** — no separate database needed.

### 8.4 Advantages

| Traditional (Separate Files) | .jcross (Unified) |
|------------------------------|-------------------|
| `program.py` reads `data.json` | One `.jcross` file |
| Data format is opaque | Data format is self-documenting |
| Schema defined separately | Schema IS the structure |
| Need serialization logic | Built-in save/load |
| Data and code can drift | Always in sync |

---

## 9. Real-World Examples

### Example 1: Puzzle Completion Detector

**Use Case**: Detect when an AI's response is complete (not cut off mid-sentence).

```jcross
"""
Response Completion Detector
Uses Cross structure to analyze text completeness
"""

CROSS response_completion_puzzle {
    // Structure patterns (Cross structure definition)
    AXIS structure_patterns {
        UP: definition {
            required: [subject, is_statement, explanation]
            optional: [examples, technical_details]
        }
        DOWN: explanation {
            required: [introduction, main_points]
            optional: [conclusion, examples]
        }
        FRONT: question {
            required: [question_word, topic]
            optional: [context, examples]
        }
    }

    // Detect structure type
    PATTERN detect_structure_type(text) {
        MATCH text {
            CONTAINS ["とは", "とはなにか", "には"] -> "definition"
            CONTAINS ["方法", "やり方", "手順"] -> "how_to"
            CONTAINS ["理由", "なぜ", "because"] -> "explanation"
            DEFAULT -> "general"
        }
    }

    // Detect which pieces are present
    FUNCTION detect_pieces(text, struct_type) {
        pieces = []

        // Subject detection
        IF CONTAINS(text, ["は、", "とは", "について"]) {
            pieces.APPEND("subject")
        }

        // Explanation detection
        IF LENGTH(text) > 50 {
            pieces.APPEND("explanation")
        }

        // Examples detection
        IF CONTAINS(text, ["例えば", "たとえば", "for example"]) {
            pieces.APPEND("examples")
        }

        RETURN pieces
    }

    // Calculate completion score
    FUNCTION calculate_score(pieces, struct_type) {
        required = structure_patterns[struct_type].required
        optional = structure_patterns[struct_type].optional

        score = 0
        total_required = LENGTH(required)
        total_optional = LENGTH(optional)

        // Required pieces: 80% weight
        FOR piece IN required {
            IF piece IN pieces {
                score = score + (0.8 / total_required)
            }
        }

        // Optional pieces: 20% weight
        FOR piece IN optional {
            IF piece IN pieces {
                score = score + (0.2 / total_optional)
            }
        }

        RETURN score
    }

    // Main completion check
    PATTERN is_complete(completion_score, text) {
        // If score >= 80%, definitely complete
        IF completion_score >= 0.8 {
            RETURN true
        }

        // Check for proper sentence endings
        proper_endings = [
            "。", "！", "？", ".",
            "す", "た", "ます", "ました"
        ]

        FOR ending IN proper_endings {
            IF ENDS_WITH(text, ending) {
                RETURN true
            }
        }

        RETURN false
    }
}
```

**Usage**:
```python
# Python bridge calls .jcross logic
detector = JCrossProcessor("response_completion_puzzle.jcross")
text = "人工知能とは、人間の知能を模倣するシステムです。"
is_done = detector.run("is_complete", completion_score=0.85, text=text)
# Returns: true
```

---

### Example 2: Todo List Manager

**Use Case**: Manage tasks with Cross structure organization.

```jcross
"""
Todo List Manager
Organizes tasks using 6-axis Cross structure
"""

CROSS todo_manager {
    // UP: Tasks to do
    AXIS UP {
        pending_tasks: []
        total_added: 0
    }

    // DOWN: Completed tasks
    AXIS DOWN {
        completed_tasks: []
        total_completed: 0
    }

    // LEFT: Time tracking
    AXIS LEFT {
        task_created_times: {}
        task_completed_times: {}
    }

    // RIGHT: Actions taken
    AXIS RIGHT {
        action_log: []
    }

    // FRONT: Current focus
    AXIS FRONT {
        active_task: null
        current_priority: "medium"
    }

    // BACK: Metadata
    AXIS BACK {
        user_id: ""
        settings: {
            auto_save: true,
            remind: false
        }
    }

    FUNCTION add_task(description, priority) {
        task_id = UP.total_added + 1
        timestamp = NOW()

        task = {
            id: task_id,
            description: description,
            priority: priority,
            created: timestamp
        }

        // Store in UP axis
        UP.pending_tasks.APPEND(task)
        UP.total_added = UP.total_added + 1

        // Track creation time
        LEFT.task_created_times[task_id] = timestamp

        // Log action
        RIGHT.action_log.APPEND({
            action: "add_task",
            task_id: task_id,
            timestamp: timestamp
        })

        SELF.save()
        RETURN task_id
    }

    FUNCTION complete_task(task_id) {
        // Find task in pending
        FOR i, task IN UP.pending_tasks {
            IF task.id == task_id {
                // Move to completed
                timestamp = NOW()
                task.completed = timestamp

                DOWN.completed_tasks.APPEND(task)
                DOWN.total_completed = DOWN.total_completed + 1

                UP.pending_tasks.REMOVE(i)

                // Track completion time
                LEFT.task_completed_times[task_id] = timestamp

                // Log action
                RIGHT.action_log.APPEND({
                    action: "complete_task",
                    task_id: task_id,
                    timestamp: timestamp
                })

                SELF.save()
                RETURN true
            }
        }

        RETURN false
    }

    FUNCTION get_pending_by_priority(priority) {
        filtered = []

        FOR task IN UP.pending_tasks {
            IF task.priority == priority {
                filtered.APPEND(task)
            }
        }

        RETURN filtered
    }

    FUNCTION get_statistics() {
        total_time = 0
        count = 0

        FOR task_id, completed_time IN LEFT.task_completed_times {
            IF task_id IN LEFT.task_created_times {
                created_time = LEFT.task_created_times[task_id]
                duration = completed_time - created_time
                total_time = total_time + duration
                count = count + 1
            }
        }

        average_time = 0
        IF count > 0 {
            average_time = total_time / count
        }

        RETURN {
            total_added: UP.total_added,
            total_completed: DOWN.total_completed,
            pending: LENGTH(UP.pending_tasks),
            average_completion_time: average_time
        }
    }
}
```

**Usage**:
```python
# Python calls .jcross functions
todo = JCrossProcessor("todo_manager.jcross")
todo.run("add_task", description="Write documentation", priority="high")
todo.run("add_task", description="Review code", priority="medium")
todo.run("complete_task", task_id=1)
stats = todo.run("get_statistics")
# Returns: { total_added: 2, total_completed: 1, pending: 1, ... }
```

---

### Example 3: Learning System

**Use Case**: Track what concepts a user has learned over time.

```jcross
"""
Learning Progress Tracker
Tracks concept mastery using Cross structure
"""

CROSS learning_system {
    // UP: Concepts to learn
    AXIS UP {
        concepts_to_learn: [
            "variables", "functions", "loops",
            "classes", "async", "patterns"
        ]
        total_concepts: 6
    }

    // DOWN: Mastered concepts
    AXIS DOWN {
        mastered_concepts: []
        mastery_scores: {}
    }

    // LEFT: Learning timeline
    AXIS LEFT {
        learning_sessions: []
        time_spent: {}
    }

    // RIGHT: Practice exercises completed
    AXIS RIGHT {
        exercises_completed: []
        exercises_passed: 0
        exercises_failed: 0
    }

    // FRONT: Current learning state
    AXIS FRONT {
        current_concept: null
        current_difficulty: "beginner"
        focus_area: ""
    }

    // BACK: User profile
    AXIS BACK {
        user_id: ""
        learning_style: "visual"
        preferred_pace: "moderate"
    }

    FUNCTION start_learning(concept) {
        timestamp = NOW()

        FRONT.current_concept = concept

        LEFT.learning_sessions.APPEND({
            concept: concept,
            started: timestamp,
            status: "in_progress"
        })

        SELF.save()
        RETURN true
    }

    FUNCTION complete_exercise(concept, passed) {
        timestamp = NOW()

        RIGHT.exercises_completed.APPEND({
            concept: concept,
            passed: passed,
            timestamp: timestamp
        })

        IF passed {
            RIGHT.exercises_passed = RIGHT.exercises_passed + 1

            // Update mastery score
            IF concept NOT IN DOWN.mastery_scores {
                DOWN.mastery_scores[concept] = 0
            }
            DOWN.mastery_scores[concept] = DOWN.mastery_scores[concept] + 10

            // Check if mastered (score >= 80)
            IF DOWN.mastery_scores[concept] >= 80 {
                IF concept NOT IN DOWN.mastered_concepts {
                    DOWN.mastered_concepts.APPEND(concept)
                    UP.concepts_to_learn.REMOVE(concept)
                }
            }
        }
        ELSE {
            RIGHT.exercises_failed = RIGHT.exercises_failed + 1
        }

        SELF.save()
        RETURN DOWN.mastery_scores[concept]
    }

    FUNCTION get_progress() {
        total = UP.total_concepts
        mastered = LENGTH(DOWN.mastered_concepts)
        remaining = LENGTH(UP.concepts_to_learn)

        progress_percent = (mastered / total) * 100

        RETURN {
            total_concepts: total,
            mastered: mastered,
            remaining: remaining,
            progress_percent: progress_percent,
            current_concept: FRONT.current_concept,
            exercises_passed: RIGHT.exercises_passed,
            exercises_failed: RIGHT.exercises_failed
        }
    }

    FUNCTION recommend_next_concept() {
        // Find concept with lowest mastery score
        lowest_score = 100
        recommended = null

        FOR concept IN UP.concepts_to_learn {
            score = 0
            IF concept IN DOWN.mastery_scores {
                score = DOWN.mastery_scores[concept]
            }

            IF score < lowest_score {
                lowest_score = score
                recommended = concept
            }
        }

        RETURN {
            concept: recommended,
            current_score: lowest_score,
            reason: "This concept needs the most practice"
        }
    }
}
```

**Usage**:
```python
learner = JCrossProcessor("learning_system.jcross")
learner.run("start_learning", concept="variables")
learner.run("complete_exercise", concept="variables", passed=True)
learner.run("complete_exercise", concept="variables", passed=True)
progress = learner.run("get_progress")
# Returns: { mastered: 0, remaining: 6, progress_percent: 0, ... }
next_up = learner.run("recommend_next_concept")
# Returns: { concept: "variables", current_score: 20, reason: "..." }
```

---

## 10. Best Practices

### 10.1 Naming Conventions

```jcross
// ✅ GOOD: Clear, descriptive names
CROSS conversation_memory { ... }
AXIS UP { user_inputs: [] }
FUNCTION log_user_input(text) { ... }

// ❌ BAD: Vague, abbreviated names
CROSS cm { ... }
AXIS A { ui: [] }
FUNCTION log(t) { ... }
```

### 10.2 Axis Organization

**Rule**: Put data where it logically belongs.

```jcross
// ✅ GOOD: Logical axis placement
CROSS chat_system {
    AXIS UP {
        user_messages: []      // Users provide input → UP
    }
    AXIS DOWN {
        ai_responses: []       // AI provides output → DOWN
    }
    AXIS LEFT {
        timestamps: []         // Time is historical → LEFT
    }
    AXIS RIGHT {
        actions_taken: []      // Actions are future-oriented → RIGHT
    }
}

// ❌ BAD: Illogical axis placement
CROSS chat_system {
    AXIS UP {
        timestamps: []         // Time is not "upward"
    }
    AXIS DOWN {
        user_messages: []      // Users don't provide "downward" input
    }
}
```

### 10.3 Function Purity

```jcross
// ✅ GOOD: Pure calculation function
FUNCTION calculate_score(pieces) {
    score = 0
    FOR piece IN pieces {
        score = score + 10
    }
    RETURN score
}

// ✅ GOOD: Clearly named side-effect function
FUNCTION save_score_to_down(score) {
    DOWN.last_score = score
    SELF.save()
    RETURN true
}

// ❌ BAD: Hidden side effects
FUNCTION calculate_score(pieces) {
    score = 0
    FOR piece IN pieces {
        score = score + 10
    }
    // Surprise! This function also saves
    DOWN.last_score = score
    SELF.save()
    RETURN score
}
```

### 10.4 Error Handling

```jcross
FUNCTION get_task(task_id) {
    FOR task IN UP.pending_tasks {
        IF task.id == task_id {
            RETURN task
        }
    }

    // Explicit error return
    RETURN {
        error: true,
        message: "Task not found",
        task_id: task_id
    }
}

// Caller checks for errors
FUNCTION complete_task(task_id) {
    task = get_task(task_id)

    IF task.error {
        RETURN task  // Propagate error
    }

    // Process task...
}
```

### 10.5 Documentation

```jcross
"""
Conversation Memory System

This .jcross file stores all conversation data and provides
functions to log inputs, responses, and query history.

Axes:
  UP: User inputs
  DOWN: AI responses
  LEFT: Timestamps
  RIGHT: Actions taken
  FRONT: Current conversation thread
  BACK: Session metadata
"""

CROSS conversation_memory {
    AXIS UP {
        user_inputs: []
    }

    /**
     * Log a user input to the conversation history
     *
     * @param user_input: String - The user's message
     * @return: Object with total_inputs and total_responses counts
     */
    FUNCTION log_user_input(user_input) {
        // Implementation...
    }
}
```

### 10.6 Keep Functions Small

```jcross
// ✅ GOOD: Small, focused functions
FUNCTION add_task(description) {
    task = create_task_object(description)
    store_task(task)
    log_action("add_task", task.id)
    RETURN task.id
}

FUNCTION create_task_object(description) {
    RETURN {
        id: UP.total_added + 1,
        description: description,
        created: NOW()
    }
}

FUNCTION store_task(task) {
    UP.pending_tasks.APPEND(task)
    UP.total_added = UP.total_added + 1
}

// ❌ BAD: Monolithic function
FUNCTION add_task(description) {
    // 50 lines of logic...
}
```

---

## 11. Advanced Techniques

### 11.1 Self-Modifying Code

.jcross files can modify their own structure:

```jcross
CROSS self_improving {
    AXIS UP {
        learning_data: []
    }

    AXIS DOWN {
        learned_patterns: []
    }

    FUNCTION learn_pattern(data) {
        // Analyze data
        pattern = analyze(data)

        // Store learned pattern
        DOWN.learned_patterns.APPEND(pattern)

        // Modify own behavior based on learning
        IF LENGTH(DOWN.learned_patterns) > 10 {
            SELF.add_function("detect_" + pattern.name, pattern.logic)
        }

        SELF.save()
        RETURN pattern
    }
}
```

### 11.2 Cross-to-Cross Communication

Multiple .jcross files can interact:

```jcross
// File: user_profile.jcross
CROSS user_profile {
    AXIS UP {
        preferences: {
            language: "en",
            theme: "dark"
        }
    }

    FUNCTION get_preference(key) {
        RETURN UP.preferences[key]
    }
}

// File: chat_system.jcross
CROSS chat_system {
    AXIS BACK {
        user_profile_path: "user_profile.jcross"
    }

    FUNCTION get_user_language() {
        // Load other .jcross file
        profile = LOAD_CROSS(BACK.user_profile_path)
        language = profile.run("get_preference", key="language")
        RETURN language
    }
}
```

### 11.3 Dynamic Pattern Creation

```jcross
CROSS dynamic_classifier {
    AXIS DOWN {
        learned_patterns: {}
    }

    FUNCTION add_pattern(name, keywords) {
        // Dynamically create a new pattern
        DOWN.learned_patterns[name] = keywords
        SELF.save()
    }

    PATTERN classify_dynamic(text) {
        // Use dynamically created patterns
        FOR pattern_name, keywords IN DOWN.learned_patterns {
            IF CONTAINS(text, keywords) {
                RETURN pattern_name
            }
        }
        DEFAULT -> "unknown"
    }
}
```

### 11.4 Fractal Cross Structures

Cross structures can contain other Cross structures:

```jcross
CROSS outer {
    AXIS UP {
        // Nested Cross structure
        inner_system: CROSS {
            AXIS UP {
                data: []
            }
            FUNCTION process() {
                RETURN "inner"
            }
        }
    }

    FUNCTION use_inner() {
        result = UP.inner_system.process()
        RETURN result
    }
}
```

### 11.5 Meta-Programming

Generate .jcross code from .jcross code:

```jcross
CROSS code_generator {
    FUNCTION generate_todo_function(field_name) {
        code = """
        FUNCTION add_to_""" + field_name + """(item) {
            UP.""" + field_name + """.APPEND(item)
            SELF.save()
            RETURN LENGTH(UP.""" + field_name + """)
        }
        """

        // Write new function to file
        SELF.add_function_from_string(code)
        SELF.save()

        RETURN code
    }
}
```

### 11.6 Time-Based Patterns

```jcross
CROSS time_aware {
    AXIS LEFT {
        event_timestamps: []
    }

    FUNCTION detect_pattern_over_time() {
        now = NOW()
        recent_events = []

        // Get events from last hour
        FOR timestamp IN LEFT.event_timestamps {
            IF now - timestamp < 3600 {
                recent_events.APPEND(timestamp)
            }
        }

        // Detect frequency pattern
        IF LENGTH(recent_events) > 10 {
            RETURN "high_frequency"
        }
        ELSE IF LENGTH(recent_events) > 5 {
            RETURN "medium_frequency"
        }
        ELSE {
            RETURN "low_frequency"
        }
    }
}
```

---

## 🎓 Conclusion

You've now learned the complete .jcross language:

1. **Philosophy**: Code, data, and logic unified in 6-axis Cross structure
2. **Syntax**: `CROSS`, `AXIS`, `FUNCTION`, `PATTERN`, `MATCH`
3. **Data Types**: Numbers, strings, booleans, arrays, objects
4. **Control Flow**: `IF`, `FOR`, `WHILE`, pattern matching
5. **Functions**: Pure functions and side-effect functions
6. **Storage**: .jcross files as self-updating databases
7. **Examples**: Real-world systems (todo list, learning tracker, completion detector)
8. **Best Practices**: Naming, axis organization, documentation
9. **Advanced**: Self-modification, cross-communication, meta-programming

### Next Steps

1. **Practice**: Write your first .jcross file
2. **Experiment**: Try using .jcross as data storage
3. **Build**: Create a real system using Cross structures
4. **Share**: Contribute to the Verantyx ecosystem

### Resources

- **Verantyx-CLI**: https://github.com/Ag3497120/verantyx-cli
- **Examples**: See `verantyx_cli/engine/*.jcross` in the repository
- **Community**: Join discussions on GitHub Issues

---

**Made with 🧠 Cross-Native Architecture**

*.jcross — Where Code, Data, and Logic Coexist*
