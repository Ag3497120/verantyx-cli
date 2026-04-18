from typing import List, Optional, Any, Dict

class Node:
    def token_literal(self):
        pass

class Statement(Node):
    pass

class Expression(Node):
    pass

# --- Root ---
class Program(Node):
    def __init__(self):
        self.statements = []
    
    def token_literal(self):
        return "PROGRAM"
    def __repr__(self):
        return f"Program({self.statements})"

# --- Top Level Declarations ---
class CrossDef(Statement):
    def __init__(self, name: 'Identifier', body: 'BlockStatement'):
        self.name = name
        self.body = body
    def __repr__(self): return f"CrossDef({self.name}, {self.body})"

class AxisDef(Statement):
    def __init__(self, name: 'Identifier', body: 'BlockStatement'):
        self.name = name
        self.body = body
    def __repr__(self): return f"AxisDef({self.name}, {self.body})"

class FuncDef(Statement):
    def __init__(self, name: 'Identifier', params: List['Identifier'], body: 'BlockStatement'):
        self.name = name
        self.params = params
        self.body = body
    def __repr__(self): return f"FuncDef({self.name}({self.params}), {self.body})"

class PatternDef(Statement):
    def __init__(self, name: 'Identifier', params: List['Identifier'], body: 'BlockStatement'):
        self.name = name
        self.params = params
        self.body = body  # Contains MatchStatement
    def __repr__(self): return f"PatternDef({self.name}({self.params}), {self.body})"

class BlockStatement(Statement):
    def __init__(self):
        self.statements = []
    def __repr__(self): return f"Block({self.statements})"

# --- Internal Statements ---
class AssignStatement(Statement):
    def __init__(self, left: Expression, value: Expression):
        self.left = left # Can be Identifier or PropAccess (e.g. UP.count)
        self.value = value
    def __repr__(self): return f"Assign({self.left} = {self.value})"

class ForInStatement(Statement):
    def __init__(self, variable: 'Identifier', iterable: Expression, body: 'BlockStatement'):
        self.variable = variable
        self.iterable = iterable
        self.body = body
    def __repr__(self): return f"ForIn({self.variable} in {self.iterable} {{ {self.body} }})"

class IfStatement(Statement):
    def __init__(self, condition: Expression, consequence: 'BlockStatement', alternative: Optional['BlockStatement']):
        self.condition = condition
        self.consequence = consequence
        self.alternative = alternative
    def __repr__(self): return f"If({self.condition} {{ {self.consequence} }} else {{ {self.alternative} }})"

class ReturnStatement(Statement):
    def __init__(self, return_value: Expression):
        self.return_value = return_value
    def __repr__(self): return f"Return({self.return_value})"

class ExpressionStatement(Statement):
    def __init__(self, expression: Expression):
        self.expression = expression
    def __repr__(self): return f"ExprStmt({self.expression})"

class MatchArm(Node):
    def __init__(self, condition_type: str, condition_expr: Optional[Expression], result_expr: Expression):
        self.condition_type = condition_type # "CONTAINS", "STARTS_WITH", "DEFAULT"
        self.condition_expr = condition_expr
        self.result_expr = result_expr
    def __repr__(self): return f"MatchArm({self.condition_type} {self.condition_expr} -> {self.result_expr})"

class MatchStatement(Statement):
    def __init__(self, subject: Expression, arms: List[MatchArm]):
        self.subject = subject
        self.arms = arms
    def __repr__(self): return f"MatchStatement({self.subject} {{ {self.arms} }})"

# --- Expressions ---
class Identifier(Expression):
    def __init__(self, value: str):
        self.value = value
    def __repr__(self): return f"Id({self.value})"

class Literal(Expression):
    def __init__(self, value: Any):
        self.value = value
    def __repr__(self): return f"Literal({self.value})"

class ArrayLiteral(Expression):
    def __init__(self, elements: List[Expression]):
        self.elements = elements
    def __repr__(self): return f"Array({self.elements})"

class DictLiteral(Expression):
    def __init__(self, pairs: Dict[str, Expression]):
        self.pairs = pairs
    def __repr__(self): return f"Dict({self.pairs})"

class BinaryExpr(Expression):
    def __init__(self, left: Expression, operator: str, right: Expression):
        self.left = left
        self.operator = operator
        self.right = right
    def __repr__(self): return f"Binary({self.left} {self.operator} {self.right})"

class CallExpr(Expression):
    def __init__(self, function: Expression, arguments: List[Expression]):
        self.function = function # Identifier or PropAccess (e.g. ARRAY.APPEND)
        self.arguments = arguments
    def __repr__(self): return f"Call({self.function}({self.arguments}))"

class LambdaExpr(Expression):
    def __init__(self, params: List['Identifier'], body: Expression):
        self.params = params
        self.body = body
    def __repr__(self): return f"Lambda({self.params} -> {self.body})"

class PropAccess(Expression):
    def __init__(self, object: Expression, property: Identifier):
        self.object = object
        self.property = property
    def __repr__(self): return f"PropAccess({self.object}.{self.property})"
