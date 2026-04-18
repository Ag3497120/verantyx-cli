import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.token import TokenType

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
while True:
    tok = lexer.next_token()
    print(tok)
    if tok.type == TokenType.EOF:
        break
