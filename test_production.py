import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser
from verantyx.jcross_lang.interpreter import JCrossInterpreter

code = """
CROSS data_processing {
    AXIS UP {
        scores: [10, -5, 20, 0, 50]
        results: []
        filtered: []
    }
    FUNCTION process() {
        // Map scores
        UP.results = UP.scores.MAP(item -> item * 2)

        // Filter scores manually via FOR IN
        FOR score IN UP.scores {
            IF score > 0 {
                UP.filtered.APPEND(score)
            }
        }
        
        return UP.filtered
    }
}
"""
lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse_program()
if parser.errors:
    print(parser.errors)
else:
    interpreter = JCrossInterpreter()
    interpreter.eval(program)
    res = interpreter.run_function("process")
    print("Function Returned:", res)
    print("Environment UP:", interpreter.env.axes["UP"])
