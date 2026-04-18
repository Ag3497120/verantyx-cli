import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser

code = "UP.scores.MAP(item -> item * 2)"
lexer = Lexer(code)
parser = Parser(lexer)
expr = parser.parse_expression(1)
print(expr)
