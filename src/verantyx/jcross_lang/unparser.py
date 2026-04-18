import verantyx.jcross_lang.ast as ast
import json

class JCrossUnparser:
    def __init__(self):
        self.indent_level = 0
        
    def indent(self):
        return "    " * self.indent_level

    def unparse_env(self, env, name="self_improving_cross"):
        # Takes the LIVE environment and serializes it back to a .jcross file!
        lines = []
        lines.append(f"CROSS {name} {{")
        self.indent_level += 1
        
        # Serialize Axes with live data
        for axis_name, axis_data in env.axes.items():
            if axis_data or axis_name in ["UP", "DOWN", "LEFT", "RIGHT", "FRONT", "BACK"]:
                lines.append(f"{self.indent()}AXIS {axis_name} {{")
                self.indent_level += 1
                for key, val in axis_data.items():
                    if isinstance(val, dict):
                        # Empty dict -> {}
                        if not val:
                            lines.append(f"{self.indent()}{key}: {{}}")
                        else:
                            # Assuming single depth or json dumps for simplicity in prototyping
                            lines.append(f"{self.indent()}{key}: {json.dumps(val, ensure_ascii=False)}")
                    elif isinstance(val, list):
                        lines.append(f"{self.indent()}{key}: " + json.dumps(val, ensure_ascii=False))
                    elif isinstance(val, str):
                        lines.append(f"{self.indent()}{key}: \"{val}\"")
                    elif isinstance(val, bool):
                        lines.append(f"{self.indent()}{key}: {'true' if val else 'false'}")
                    elif val is None:
                        lines.append(f"{self.indent()}{key}: null")
                    else:
                        lines.append(f"{self.indent()}{key}: {val}")
                self.indent_level -= 1
                lines.append(f"{self.indent()}}}")
                lines.append("")
        
        # Serialize Functions and Patterns straight from AST
        for func_name, func_node in env.functions.items():
            lines.append(self.unparse_node(func_node))
            lines.append("")
            
        self.indent_level -= 1
        lines.append("}")
        return "\n".join(lines)
        
    def unparse_node(self, node: ast.Node) -> str:
        if isinstance(node, ast.FuncDef):
            params = ", ".join(p.value for p in node.params)
            res = f"{self.indent()}FUNCTION {node.name.value}({params}) {{\n"
            self.indent_level += 1
            res += self.unparse_block(node.body)
            self.indent_level -= 1
            res += f"\n{self.indent()}}}"
            return res
            
        elif isinstance(node, ast.PatternDef):
            params = ", ".join(p.value for p in node.params)
            res = f"{self.indent()}PATTERN {node.name.value}({params}) {{\n"
            self.indent_level += 1
            res += self.unparse_block(node.body)
            self.indent_level -= 1
            res += f"\n{self.indent()}}}"
            return res
            
        elif isinstance(node, ast.MatchStatement):
            res = f"{self.indent()}MATCH {self.unparse_expr(node.subject)} {{\n"
            self.indent_level += 1
            for arm in node.arms:
                if arm.condition_type == "DEFAULT":
                    res += f"{self.indent()}DEFAULT -> {self.unparse_expr(arm.result_expr)}\n"
                elif arm.condition_type in ["CONTAINS", "STARTS_WITH"]:
                    res += f"{self.indent()}{arm.condition_type} {self.unparse_expr(arm.condition_expr)} -> {self.unparse_expr(arm.result_expr)}\n"
            self.indent_level -= 1
            res += f"{self.indent()}}}"
            return res
            
        elif isinstance(node, ast.AssignStatement):
            return f"{self.indent()}{self.unparse_expr(node.left)} = {self.unparse_expr(node.value)}"
            
        elif isinstance(node, ast.ReturnStatement):
            return f"{self.indent()}RETURN {self.unparse_expr(node.return_value)}"
            
        elif isinstance(node, ast.ExpressionStatement):
            return f"{self.indent()}{self.unparse_expr(node.expression)}"
            
        return f"{self.indent()}// Unknown statement"

    def unparse_block(self, block: ast.BlockStatement) -> str:
        lines = []
        for stmt in block.statements:
            lines.append(self.unparse_node(stmt))
        return "\n".join(lines)

    def unparse_expr(self, expr: ast.Expression) -> str:
        if isinstance(expr, ast.Identifier):
            return expr.value
        elif isinstance(expr, ast.Literal):
            if isinstance(expr.value, str):
                return f'"{expr.value}"'
            elif isinstance(expr.value, bool):
                return "true" if expr.value else "false"
            elif expr.value is None:
                return "null"
            return str(expr.value)
        elif isinstance(expr, ast.ArrayLiteral):
            elems = ", ".join(self.unparse_expr(e) for e in expr.elements)
            return f"[{elems}]"
        elif isinstance(expr, ast.BinaryExpr):
            return f"{self.unparse_expr(expr.left)} {expr.operator} {self.unparse_expr(expr.right)}"
        elif isinstance(expr, ast.PropAccess):
            if isinstance(expr.object, ast.Identifier):
                return f"{expr.object.value}.{expr.property.value}" # UP.count
            return f"{self.unparse_expr(expr.object)}.{expr.property.value}"
        elif isinstance(expr, ast.CallExpr):
            args = ", ".join(self.unparse_expr(a) for a in expr.arguments)
            return f"{self.unparse_expr(expr.function)}({args})"
        return "<?>"
