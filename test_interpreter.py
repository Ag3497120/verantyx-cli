import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser
from verantyx.jcross_lang.interpreter import JCrossInterpreter

code = """
CROSS todo_manager {
    AXIS UP {
        pending: []
        count: 0
    }
    FUNCTION add(task) {
        UP.pending.APPEND(task)
        UP.count = UP.count + 1
        RETURN UP.count
    }
}
"""
lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse_program()

interpreter = JCrossInterpreter()
interpreter.eval(program)

print("--- Initial State ---")
print(interpreter.env.axes)

print("\n--- Calling function add('Buy Milk') ---")
res = interpreter.run_function("add", "Buy Milk")
print("Returned:", res)
print("Axes:", interpreter.env.axes)

print("\n--- Calling function add('Buy Eggs') ---")
res = interpreter.run_function("add", "Buy Eggs")
print("Returned:", res)
print("Axes:", interpreter.env.axes)
