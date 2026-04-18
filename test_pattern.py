import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser
from verantyx.jcross_lang.interpreter import JCrossInterpreter

code = """
CROSS response_detector {
    PATTERN classify_text(text) {
        MATCH text {
            CONTAINS ["error", "fail"] -> "error_report"
            CONTAINS ["success", "complete"] -> "success_message"
            STARTS_WITH "Question:" -> "user_query"
            DEFAULT -> "unknown"
        }
    }
}
"""
lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse_program()

interpreter = JCrossInterpreter()
interpreter.eval(program)

res1 = interpreter.run_function("classify_text", "System error 404")
print("Response 1:", res1)

res2 = interpreter.run_function("classify_text", "Backup complete successfully")
print("Response 2:", res2)

res3 = interpreter.run_function("classify_text", "Question: How do I save?")
print("Response 3:", res3)

res4 = interpreter.run_function("classify_text", "Random string")
print("Response 4:", res4)

