import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.jcross_lang.lexer import Lexer
from verantyx.jcross_lang.parser import Parser
from verantyx.jcross_lang.interpreter import JCrossInterpreter

code = """
CROSS iteration_test {
    FUNCTION check_all(list) {
        FOR item IN list {
            UP.log.APPEND(item)
        }
    }
}
"""
