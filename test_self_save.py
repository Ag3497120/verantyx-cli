import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser
from verantyx.jcross_lang.interpreter import JCrossInterpreter

code = """
CROSS self_storing_data {
    AXIS UP {
        data: []
    }
    FUNCTION learn(topic) {
        UP.data.APPEND(topic)
        SELF.save()
        return UP.data
    }
}
"""
lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse_program()

file_path = "output_self_save.jcross"
interpreter = JCrossInterpreter(file_path=file_path)
interpreter.eval(program)
print("Before logic")

interpreter.run_function("learn", "Cognitive Architecture")
interpreter.run_function("learn", "JCross Syntax")

print("Generated file content:")
with open(file_path, "r") as f:
    print(f.read())
