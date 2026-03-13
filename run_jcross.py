#!/usr/bin/env python3
"""Simple .jcross file runner using Stage 2 interpreter"""

import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python3 run_jcross.py <file.jcross>")
    sys.exit(1)

jcross_file = sys.argv[1]

# Use bootstrap interpreter
sys.path.insert(0, str(Path(__file__).parent / 'bootstrap'))

# Import the interpreter from bootstrap
try:
    from interpreter_stage2 import JCrossInterpreter

    print(f"Running {jcross_file}...")
    print()

    interp = JCrossInterpreter()
    result = interp.load_and_execute(jcross_file)

    print()
    print(f"✅ Execution complete!")

except ImportError:
    # Fallback: direct Python execution
    print("Using direct execution...")
    with open(jcross_file, 'r') as f:
        code = f.read()

    # Simple execution: just run PRINT statements
    for line in code.split('\n'):
        line = line.strip()
        if line.startswith('PRINT('):
            # Extract print content
            content = line[6:-1]  # Remove PRINT( and )
            try:
                # Evaluate simple expressions
                result = eval(content)
                print(result)
            except:
                print(content.strip('"').strip("'"))
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
