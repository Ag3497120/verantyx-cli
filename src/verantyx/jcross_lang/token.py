from enum import Enum, auto

class TokenType(Enum):
    # Keywords
    CROSS = auto()
    AXIS = auto()
    FUNCTION = auto()
    PATTERN = auto()
    MATCH = auto()
    IF = auto()
    ELSE = auto()
    RETURN = auto()
    FOR = auto()
    IN = auto()
    DEFAULT = auto()
    CONTAINS = auto()
    STARTS_WITH = auto()

    # Types
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    NULL = auto()

    # Punctuation
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    LBRACKET = auto()   # [
    RBRACKET = auto()   # ]
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    COLON = auto()      # :
    COMMA = auto()      # ,
    DOT = auto()        # .

    # Operators
    ASSIGN = auto()     # =
    ARROW = auto()      # ->
    PLUS = auto()       # +
    MINUS = auto()      # -
    MULTIPLY = auto()   # *
    DIVIDE = auto()     # /
    GT = auto()         # >
    LT = auto()         # <
    GTE = auto()        # >=
    LTE = auto()        # <=
    EQ = auto()         # ==
    NEQ = auto()        # !=
    AND = auto()        # & 
    OR = auto()         # |

    EOF = auto()

class Token:
    def __init__(self, type: TokenType, literal: str, line: int):
        self.type = type
        self.literal = literal
        self.line = line

    def __repr__(self):
        return f"Token({self.type.name}, '{self.literal}', line {self.line})"
