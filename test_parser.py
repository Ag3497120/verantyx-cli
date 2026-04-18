import sys
import os
import pprint
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser

code = """
CROSS todo_manager {
    AXIS UP {
        pending: []
        count: 0
    }
    FUNCTION add(task) {
        // add item
        UP.pending.APPEND(task)
        UP.count = UP.count + 1
        RETURN UP.count
    }
}
"""
lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse_program()

if parser.errors:
    print("Parser errors:")
    for err in parser.errors:
        print(err)
else:
    print("AST Built Successfully!")
    for stmt in program.statements:
        print(stmt)
