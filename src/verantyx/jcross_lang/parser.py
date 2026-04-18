from typing import List, Optional, Dict
from .token import Token, TokenType
from .lexer import Lexer
import verantyx.jcross_lang.ast as ast

# Pratt Parsing Precedences
LOWEST = 1
EQUALS = 2       # ==
LESSGREATER = 3  # > or <
SUM = 4          # +
PRODUCT = 5      # *
PREFIX = 6       # -X or !X
CALL = 7         # myFunction(X)
INDEX = 8        # array[index] or obj.prop

PRECEDENCES = {
    TokenType.EQ: EQUALS,
    TokenType.NEQ: EQUALS,
    TokenType.LT: LESSGREATER,
    TokenType.GT: LESSGREATER,
    TokenType.LTE: LESSGREATER,
    TokenType.GTE: LESSGREATER,
    TokenType.PLUS: SUM,
    TokenType.MINUS: SUM,
    TokenType.MULTIPLY: PRODUCT,
    TokenType.DIVIDE: PRODUCT,
    TokenType.LPAREN: CALL,
    TokenType.LBRACKET: INDEX,
    TokenType.DOT: INDEX,
}

class Parser:
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.errors = []
        
        self.cur_token = None
        self.peek_token = None
        
        # Read two tokens to populate cur and peek
        self.next_token()
        self.next_token()

    def next_token(self):
        self.cur_token = self.peek_token
        self.peek_token = self.lexer.next_token()

    def peek_precedence(self):
        return PRECEDENCES.get(self.peek_token.type, LOWEST)

    def cur_precedence(self):
        return PRECEDENCES.get(self.cur_token.type, LOWEST)

    def parse_program(self) -> ast.Program:
        program = ast.Program()
        while self.cur_token.type != TokenType.EOF:
            stmt = self.parse_statement()
            if stmt:
                program.statements.append(stmt)
            self.next_token()
        return program

    def parse_statement(self) -> Optional[ast.Statement]:
        if self.cur_token.type == TokenType.CROSS:
            return self.parse_cross_def()
        elif self.cur_token.type == TokenType.AXIS:
            return self.parse_axis_def()
        elif self.cur_token.type == TokenType.FUNCTION:
            return self.parse_func_def()
        elif self.cur_token.type == TokenType.PATTERN:
            return self.parse_pattern_def()
        elif self.cur_token.type == TokenType.MATCH:
            return self.parse_match_statement()
        elif self.cur_token.type == TokenType.FOR:
            return self.parse_for_statement()
        elif self.cur_token.type == TokenType.IF:
            return self.parse_if_statement()
        elif self.cur_token.type == TokenType.RETURN:
            return self.parse_return_statement()
            
        # If it's an IDENTIFIER followed by ASSIGN (x = 5) or PropAccess followed by ASSIGN (UP.x = 5)
        # We parse an expression first, then check if it's followed by ASSIGN
        return self.parse_expression_or_assignment()

    def parse_cross_def(self) -> ast.CrossDef:
        # CROSS name { body }
        self.next_token() # skip CROSS
        name = ast.Identifier(self.cur_token.literal)
        self.next_token() # skip name
        
        if self.cur_token.type != TokenType.LBRACE:
            self.errors.append(f"Expected LBRACE for CROSS {name.value} [Auto-Healing]")
        
        body = self.parse_block_statement()
        return ast.CrossDef(name, body)

    def parse_axis_def(self) -> ast.AxisDef:
        # AXIS UP { body }
        self.next_token() # skip AXIS
        name = ast.Identifier(self.cur_token.literal)
        self.next_token() # skip name
        
        if self.cur_token.type != TokenType.LBRACE:
            self.errors.append(f"Expected LBRACE for AXIS {name.value} [Auto-Healing]")
            
        body = self.parse_block_statement(is_data_block=True)
        return ast.AxisDef(name, body)

    def parse_func_def(self) -> ast.FuncDef:
        # FUNCTION name(p1, p2) { body }
        self.next_token()
        name = ast.Identifier(self.cur_token.literal)
        self.next_token()
        
        if self.cur_token.type != TokenType.LPAREN:
            self.errors.append("Expected LPAREN")
            return None
            
        params = []
        self.next_token() # skip (
        while self.cur_token.type != TokenType.RPAREN and self.cur_token.type != TokenType.EOF:
            if self.cur_token.type == TokenType.IDENTIFIER:
                params.append(ast.Identifier(self.cur_token.literal))
            self.next_token()
            if self.cur_token.type == TokenType.COMMA:
                self.next_token()
                
        self.next_token() # skip )
        
        if self.cur_token.type != TokenType.LBRACE:
            self.errors.append(f"Expected LBRACE for FUNC {name.value} [Auto-Healing]")
            
        body = self.parse_block_statement()
        return ast.FuncDef(name, params, body)

    def parse_pattern_def(self) -> ast.PatternDef:
        # PATTERN name(p1) { body }
        self.next_token()
        name = ast.Identifier(self.cur_token.literal)
        self.next_token()
        
        if self.cur_token.type != TokenType.LPAREN:
            self.errors.append("Expected LPAREN")
            return None
            
        params = []
        self.next_token() # skip (
        while self.cur_token.type != TokenType.RPAREN and self.cur_token.type != TokenType.EOF:
            if self.cur_token.type == TokenType.IDENTIFIER:
                params.append(ast.Identifier(self.cur_token.literal))
            self.next_token()
            if self.cur_token.type == TokenType.COMMA:
                self.next_token()
                
        self.next_token() # skip )
        
        if self.cur_token.type != TokenType.LBRACE:
            self.errors.append(f"Expected LBRACE for PATTERN {name.value} [Auto-Healing]")
            
        body = self.parse_block_statement()
        return ast.PatternDef(name, params, body)

    def parse_match_statement(self) -> ast.MatchStatement:
        # MATCH subject { arms }
        self.next_token() # skip MATCH
        subject = self.parse_expression(LOWEST)
        
        if self.peek_token.type != TokenType.LBRACE:
            self.errors.append("Expected LBRACE after MATCH subject [Auto-Healing]")
        else:
            self.next_token() # goto LBRACE
        self.next_token() # goto first arm condition
        
        arms = []
        while self.cur_token.type != TokenType.RBRACE and self.cur_token.type != TokenType.EOF:
            cond_type = self.cur_token.literal # CONTAINS, STARTS_WITH, DEFAULT
            self.next_token()
            
            cond_expr = None
            if cond_type != "DEFAULT":
                cond_expr = self.parse_expression(LOWEST)
                self.next_token() # skip to ARROW
                
            if self.cur_token.type != TokenType.ARROW:
                self.errors.append(f"Expected ARROW, got {self.cur_token.literal}")
                
            self.next_token() # skip ARROW
            result_expr = self.parse_expression(LOWEST)
            
            arms.append(ast.MatchArm(cond_type, cond_expr, result_expr))
            self.next_token() # advance to next arm
            
        return ast.MatchStatement(subject, arms)

    def parse_for_statement(self) -> ast.ForInStatement:
        # FOR item IN list { body }
        self.next_token() # skip FOR
        
        if self.cur_token.type != TokenType.IDENTIFIER:
            self.errors.append("Expected IDENTIFIER after FOR")
            return None
        var_name = ast.Identifier(self.cur_token.literal)
        self.next_token()
        
        if self.cur_token.type != TokenType.IN:
            self.errors.append("Expected IN after FOR variable")
            return None
        self.next_token() # goto iterable expr
        
        iterable = self.parse_expression(LOWEST)
        
        if self.peek_token.type != TokenType.LBRACE:
            self.errors.append("Expected LBRACE after FOR iterable [Auto-Healing]")
        else:
            self.next_token() # goto LBRACE
        
        body = self.parse_block_statement()
        return ast.ForInStatement(var_name, iterable, body)

    def parse_if_statement(self) -> ast.IfStatement:
        # IF condition { consequence } ELSE { alternative }
        self.next_token() # skip IF
        
        condition = self.parse_expression(LOWEST)
        
        if self.peek_token.type != TokenType.LBRACE:
            self.errors.append("Expected LBRACE after IF condition [Auto-Healing]")
        else:
            self.next_token() # to LBRACE
        
        consequence = self.parse_block_statement()
        alternative = None
        
        if self.peek_token.type == TokenType.ELSE:
            self.next_token() # to ELSE
            
            if self.peek_token.type == TokenType.IF:
                # Handle ELSE IF by recursively parsing the IF and wrapping it in a block
                self.next_token() # to IF
                if_stmt = self.parse_if_statement()
                alt_block = ast.BlockStatement()
                if if_stmt: alt_block.statements.append(if_stmt)
                alternative = alt_block
            else:
                if self.peek_token.type != TokenType.LBRACE:
                    self.errors.append("Expected LBRACE after ELSE [Auto-Healing]")
                else:
                    self.next_token() # to LBRACE
                alternative = self.parse_block_statement()
                
        return ast.IfStatement(condition, consequence, alternative)

    def parse_return_statement(self) -> ast.ReturnStatement:
        self.next_token() # skip RETURN
        expr = self.parse_expression(LOWEST)
        return ast.ReturnStatement(expr)

    def parse_expression_or_assignment(self) -> ast.Statement:
        expr = self.parse_expression(LOWEST)
        
        if self.peek_token.type == TokenType.ASSIGN:
            self.next_token() # Advance to ASSIGN
            self.next_token() # Advance to RHS
            value = self.parse_expression(LOWEST)
            return ast.AssignStatement(expr, value)
            
        # Notice in JCross syntax, dictionary keys act as assignments inside Axis blocks:
        # pending: [] 
        if self.peek_token.type == TokenType.COLON and isinstance(expr, ast.Identifier):
            self.next_token() # Advance to COLON
            self.next_token() # Advance to RHS
            value = self.parse_expression(LOWEST)
            return ast.AssignStatement(expr, value)

        return ast.ExpressionStatement(expr)

    def parse_block_statement(self, is_data_block=False) -> ast.BlockStatement:
        block = ast.BlockStatement()
        if self.cur_token.type == TokenType.LBRACE:
            self.next_token() # skip {
        
        while self.cur_token.type not in (TokenType.RBRACE, TokenType.EOF):
            stmt = self.parse_statement()
            if stmt:
                block.statements.append(stmt)
            self.next_token()
            
        return block

    def parse_expression(self, precedence) -> ast.Expression:
        # Check for Lambda form: item -> item.score
        if self.cur_token.type == TokenType.IDENTIFIER and self.peek_token.type == TokenType.ARROW:
            var_name = ast.Identifier(self.cur_token.literal)
            self.next_token() # skip identifier
            self.next_token() # skip arrow
            body = self.parse_expression(LOWEST)
            return ast.LambdaExpr([var_name], body)
            
        # Pratt parsing prefix
        left_exp = None
        
        if self.cur_token.type == TokenType.IDENTIFIER:
            left_exp = ast.Identifier(self.cur_token.literal)
        elif self.cur_token.type == TokenType.NUMBER:
            left_exp = ast.Literal(float(self.cur_token.literal) if '.' in self.cur_token.literal else int(self.cur_token.literal))
        elif self.cur_token.type == TokenType.STRING:
            left_exp = ast.Literal(self.cur_token.literal)
        elif self.cur_token.type == TokenType.BOOLEAN:
            left_exp = ast.Literal(self.cur_token.literal == "true")
        elif self.cur_token.type == TokenType.NULL:
            left_exp = ast.Literal(None)
        elif self.cur_token.type == TokenType.LBRACKET:
            left_exp = self.parse_array_literal()
        elif self.cur_token.type == TokenType.LBRACE:
            left_exp = self.parse_dict_literal()
            
        if not left_exp:
            self.errors.append(f"No prefix parse function for {self.cur_token.type}")
            return None

        # Pratt parsing infix
        while self.peek_token.type != TokenType.EOF and precedence < self.peek_precedence():
            if self.peek_token.type in (TokenType.PLUS, TokenType.MINUS, TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
                self.next_token()
                left_exp = self.parse_infix_expression(left_exp)
            elif self.peek_token.type == TokenType.DOT:
                self.next_token()
                left_exp = self.parse_prop_access(left_exp)
            elif self.peek_token.type == TokenType.LPAREN:
                self.next_token()
                left_exp = self.parse_call_expression(left_exp)
            else:
                break
                
        return left_exp

    def parse_infix_expression(self, left: ast.Expression) -> ast.Expression:
        operator = self.cur_token.literal
        prec = self.cur_precedence()
        self.next_token()
        right = self.parse_expression(prec)
        return ast.BinaryExpr(left, operator, right)

    def parse_prop_access(self, left: ast.Expression) -> ast.Expression:
        # cur is DOT. left is the obj.
        self.next_token() # skip dot
        prop = ast.Identifier(self.cur_token.literal)
        return ast.PropAccess(left, prop)

    def parse_call_expression(self, function: ast.Expression) -> ast.Expression:
        # cur is LPAREN. function is the identifier or propaccess.
        args = []
        self.next_token() # skip (
        while self.cur_token.type != TokenType.RPAREN and self.cur_token.type != TokenType.EOF:
            args.append(self.parse_expression(LOWEST))
            self.next_token()
            if self.cur_token.type == TokenType.COMMA:
                self.next_token()
                
        return ast.CallExpr(function, args)

    def parse_array_literal(self) -> ast.Expression:
        elements = []
        self.next_token() # skip [
        while self.cur_token.type != TokenType.RBRACKET and self.cur_token.type != TokenType.EOF:
            elements.append(self.parse_expression(LOWEST))
            self.next_token()
            if self.cur_token.type == TokenType.COMMA:
                self.next_token()
        return ast.ArrayLiteral(elements)
        
    def parse_dict_literal(self) -> ast.Expression:
        pairs = {}
        self.next_token() # skip {
        while self.cur_token.type != TokenType.RBRACE and self.cur_token.type != TokenType.EOF:
            key = self.cur_token.literal
            self.next_token() # skip key
            if self.cur_token.type == TokenType.COLON:
                self.next_token() # skip colon
            val = self.parse_expression(LOWEST)
            pairs[key] = val
            self.next_token()
            if self.cur_token.type == TokenType.COMMA:
                self.next_token()
        return ast.DictLiteral(pairs)
