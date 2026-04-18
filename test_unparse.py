import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser
from verantyx.jcross_lang.interpreter import JCrossInterpreter
from verantyx.jcross_lang.unparser import JCrossUnparser

code = """
CROSS todo_manager {
    AXIS UP {
        pending: []
        count: 0
    }
    FUNCTION add(task) {
        UP.pending.APPEND(task)
        UP.count = UP.count + 1
        return UP.count
    }
}
"""
lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse_program()

interpreter = JCrossInterpreter()
interpreter.eval(program)
interpreter.run_function("add", "Write documentation")
interpreter.run_function("add", "Launch to space")

print("--- Live Environment Dump ---")
unparser = JCrossUnparser()
rendered = unparser.unparse_env(interpreter.env, "todo_manager")
print(rendered)
