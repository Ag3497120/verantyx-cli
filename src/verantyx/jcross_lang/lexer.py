import re
from .token import Token, TokenType

KEYWORDS = {
    "CROSS": TokenType.CROSS,
    "AXIS": TokenType.AXIS,
    "FUNCTION": TokenType.FUNCTION,
    "PATTERN": TokenType.PATTERN,
    "MATCH": TokenType.MATCH,
    "IF": TokenType.IF,
    "ELSE": TokenType.ELSE,
    "RETURN": TokenType.RETURN,
    "FOR": TokenType.FOR,
    "IN": TokenType.IN,
    "DEFAULT": TokenType.DEFAULT,
    "CONTAINS": TokenType.CONTAINS,
    "STARTS_WITH": TokenType.STARTS_WITH,
    "true": TokenType.BOOLEAN,
    "false": TokenType.BOOLEAN,
    "null": TokenType.NULL
}

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.read_position = 0
        self.ch = ''
        self.line = 1
        self.read_char()

    def read_char(self):
        if self.read_position >= len(self.source):
            self.ch = ''
        else:
            self.ch = self.source[self.read_position]
        self.position = self.read_position
        self.read_position += 1

    def peek_char(self):
        if self.read_position >= len(self.source):
            return ''
        return self.source[self.read_position]

    def skip_whitespace_and_comments(self):
        while self.ch:
            if self.ch in (' ', '\t', '\r'):
                self.read_char()
            elif self.ch == '\n':
                self.line += 1
                self.read_char()
            elif self.ch == '/' and self.peek_char() == '/':
                # Single line comment
                while self.ch and self.ch != '\n':
                    self.read_char()
            elif self.ch == '/' and self.peek_char() == '*':
                # Multi-line comment block
                self.read_char()
                self.read_char()
                while self.ch:
                    if self.ch == '\n':
                        self.line += 1
                    if self.ch == '*' and self.peek_char() == '/':
                        self.read_char()
                        self.read_char()
                        break
                    self.read_char()
            else:
                break

    def read_identifier(self):
        start = self.position
        while self.ch and (self.ch.isalnum() or self.ch == '_'):
            self.read_char()
        return self.source[start:self.position]

    def read_number(self):
        start = self.position
        # Handle negatives and floats
        if self.ch == '-':
            self.read_char()
        while self.ch and (self.ch.isdigit() or self.ch == '.'):
            self.read_char()
        return self.source[start:self.position]

    def read_string(self):
        # We handle single line quotes " and ', as well as multi-line """ 
        quote_type = self.ch
        is_multiline = False
        
        # Check for """ or '''
        if self.peek_char() == quote_type and self.read_position + 1 < len(self.source) and self.source[self.read_position + 1] == quote_type:
            is_multiline = True
            self.read_char() # sip second quote
            self.read_char() # skip third quote
            
        start = self.position + 1
        self.read_char() # skip opening quote
        
        literal_chars = []
        while self.ch:
            if is_multiline:
                if self.ch == quote_type and self.peek_char() == quote_type and self.read_position + 1 < len(self.source) and self.source[self.read_position + 1] == quote_type:
                    self.read_char() # jump past 2
                    self.read_char() # jump past 3
                    break
            else:
                if self.ch == quote_type:
                    break
            
            if self.ch == '\n':
                self.line += 1
                
            literal_chars.append(self.ch)
            self.read_char()

        self.read_char() # skip closing quote
        return "".join(literal_chars)

    def next_token(self) -> Token:
        self.skip_whitespace_and_comments()

        tok = None
        if self.ch == '':
            tok = Token(TokenType.EOF, "", self.line)
        elif self.ch == '{':
            tok = Token(TokenType.LBRACE, self.ch, self.line)
        elif self.ch == '}':
            tok = Token(TokenType.RBRACE, self.ch, self.line)
        elif self.ch == '[':
            tok = Token(TokenType.LBRACKET, self.ch, self.line)
        elif self.ch == ']':
            tok = Token(TokenType.RBRACKET, self.ch, self.line)
        elif self.ch == '(':
            tok = Token(TokenType.LPAREN, self.ch, self.line)
        elif self.ch == ')':
            tok = Token(TokenType.RPAREN, self.ch, self.line)
        elif self.ch == ':':
            tok = Token(TokenType.COLON, self.ch, self.line)
        elif self.ch == ',':
            tok = Token(TokenType.COMMA, self.ch, self.line)
        elif self.ch == '.':
            tok = Token(TokenType.DOT, self.ch, self.line)
        elif self.ch == '+':
            tok = Token(TokenType.PLUS, self.ch, self.line)
        elif self.ch == '*':
            tok = Token(TokenType.MULTIPLY, self.ch, self.line)
        elif self.ch == '/':
            if self.peek_char() == '/' or self.peek_char() == '*':
                # Comments are handled in skip_whitespace_and_comments
                pass
            else:
                tok = Token(TokenType.DIVIDE, self.ch, self.line)
        elif self.ch == '-':
            if self.peek_char() == '>':
                ch = self.ch
                self.read_char()
                tok = Token(TokenType.ARROW, ch + self.ch, self.line)
            # Check if this is a negative number vs a minus operator
            elif self.peek_char().isdigit():
                # For negative numbers, we'll let read_number handle the minus sign
                # unless there's whitespace separating the negative sign from the number
                literal = self.read_number()
                return Token(TokenType.NUMBER, literal, self.line)
            else:
                tok = Token(TokenType.MINUS, self.ch, self.line)
        elif self.ch == '=':
            if self.peek_char() == '=':
                ch = self.ch
                self.read_char()
                tok = Token(TokenType.EQ, ch + self.ch, self.line)
            else:
                tok = Token(TokenType.ASSIGN, self.ch, self.line)
        elif self.ch == '!':
            if self.peek_char() == '=':
                ch = self.ch
                self.read_char()
                tok = Token(TokenType.NEQ, ch + self.ch, self.line)
        elif self.ch == '>':
            if self.peek_char() == '=':
                ch = self.ch
                self.read_char()
                tok = Token(TokenType.GTE, ch + self.ch, self.line)
            else:
                tok = Token(TokenType.GT, self.ch, self.line)
        elif self.ch == '<':
            if self.peek_char() == '=':
                ch = self.ch
                self.read_char()
                tok = Token(TokenType.LTE, ch + self.ch, self.line)
            else:
                tok = Token(TokenType.LT, self.ch, self.line)
        elif self.ch == '"' or self.ch == "'":
            literal = self.read_string()
            return Token(TokenType.STRING, literal, self.line)
        elif self.ch.isalpha() or self.ch == '_':
            literal = self.read_identifier()
            tok_type = KEYWORDS.get(literal, TokenType.IDENTIFIER)
            return Token(tok_type, literal, self.line)
        elif self.ch.isdigit():
            literal = self.read_number()
            return Token(TokenType.NUMBER, literal, self.line)
        else:
            # Fallback for unknown symbols / raw text
            tok = Token(TokenType.IDENTIFIER, self.ch, self.line)

        self.read_char()
        return tok
