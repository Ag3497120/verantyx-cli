#!/usr/bin/env python3
"""Test spatial transformation .jcross file"""

from verantyx_cli.engine.jcross_function_executor import JCrossFunctionExecutor

print("Testing spatial_transformation.jcross...")
print()

executor = JCrossFunctionExecutor()
result = executor.execute_file('jcross/spatial_transformation.jcross')

print()
print("Execution complete!")
print(f"Variables: {len(result.keys() if result else 0)}")
