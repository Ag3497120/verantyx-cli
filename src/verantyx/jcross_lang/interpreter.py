import verantyx.jcross_lang.ast as ast
from typing import Any, Dict

class TensionPrimitive:
    def __init__(self, target_name: str):
        self.target_name = target_name
        self.state = "欠落"
        print(f"  [⚠️ TENSION GENERATED] Concept/Variable missing in local geometry: '{self.target_name}'")
        
    def __str__(self):
        return f"[TENSION: {self.target_name}]"
        
    def __bool__(self):
        return False # Native tension equates to missing/Falsy
        
    def __add__(self, other):
        return other if isinstance(other, (int, float)) else 0.0
        
    def __radd__(self, other):
        return other if isinstance(other, (int, float)) else 0.0
        
    def __sub__(self, other):
        return -other if isinstance(other, (int, float)) else 0.0
        
    def __rsub__(self, other):
        return other if isinstance(other, (int, float)) else 0.0
        
    def __mul__(self, other):
        return 0.0
        
    def __rmul__(self, other):
        return 0.0
        
    def __truediv__(self, other):
        return 0.0
        
    def __rtruediv__(self, other):
        return 0.0

class CrossEnvironment:
    def __init__(self):
        # 6-Axis Storage
        self.axes = {
            "UP": {},
            "DOWN": {},
            "LEFT": {},
            "RIGHT": {},
            "FRONT": {},
            "BACK": {}
        }
        
        # Function closures
        self.functions = {}
        
        # Local variables inside a function scope
        self.locals = {}
        
        # Central Registry for Active Engine Tensions (Visualization)
        self.active_tensions = []

    def get_var(self, name: str) -> Any:
        if name in self.locals:
            return self.locals[name]
        if name in self.functions:
            return self.functions[name]
        if name in self.axes:
            return self.axes[name]
            
        # Exception Detour: Generate Tension and track it
        tension = TensionPrimitive(name)
        self.active_tensions.append(tension)
        return tension

    def set_var(self, name: str, value: Any):
        self.locals[name] = value

class JCrossInterpreter:
    def __init__(self, file_path="self.jcross", memory_bridge=None):
        self.env = CrossEnvironment()
        self.file_path = file_path
        self.memory_bridge = memory_bridge

    def eval(self, node: ast.Node) -> Any:
        if isinstance(node, ast.Program):
            result = None
            for stmt in node.statements:
                result = self.eval(stmt)
            return result

        elif isinstance(node, ast.CrossDef):
            # Mount the cross structure
            for stmt in node.body.statements:
                self.eval(stmt)

        elif isinstance(node, ast.AxisDef):
            axis_name = node.name.value
            if axis_name not in self.env.axes:
                self.env.axes[axis_name] = {}
            
            # Evaluate the assignments inside the axis block
            for stmt in node.body.statements:
                if isinstance(stmt, ast.AssignStatement):
                    key = stmt.left.value if isinstance(stmt.left, ast.Identifier) else None
                    if key:
                        val = self.eval(stmt.value)
                        self.env.axes[axis_name][key] = val

        elif isinstance(node, ast.FuncDef) or isinstance(node, ast.PatternDef):
            # Register function/pattern logic in the environment
            self.env.functions[node.name.value] = node

        elif isinstance(node, ast.MatchStatement):
            subject_val = self.eval(node.subject)
            if not isinstance(subject_val, str):
                subject_val = str(subject_val) # Cast to string for matching
                
            for arm in node.arms:
                if arm.condition_type == "DEFAULT":
                    return self.eval(arm.result_expr)
                    
                cond_val = self.eval(arm.condition_expr)
                
                if arm.condition_type == "CONTAINS":
                    # Check if any element of the list exists in the subject
                    if isinstance(cond_val, list):
                        if any(c in subject_val for c in cond_val):
                            return self.eval(arm.result_expr)
                    elif isinstance(cond_val, str):
                        if cond_val in subject_val:
                            return self.eval(arm.result_expr)
                            
                elif arm.condition_type == "STARTS_WITH":
                    if isinstance(cond_val, str) and subject_val.startswith(cond_val):
                        return self.eval(arm.result_expr)

            return None # Fallback if no match

        elif isinstance(node, ast.BlockStatement):
            result = None
            for stmt in node.statements:
                result = self.eval(stmt)
                # If we hit a return statement, bubble it up
                if isinstance(stmt, ast.ReturnStatement):
                    return result
            return result
            
        elif isinstance(node, ast.ForInStatement):
            iterable_val = self.eval(node.iterable)
            if not isinstance(iterable_val, (list, tuple)):
                # If not an array, maybe a dict? JCross spec says we can do:
                # FOR key, val IN dict
                # But our ForInStatement only supports single variable (item).
                # We'll just assume it's a list for prototyping.
                iterable_val = []
                
            var_name = node.variable.value
            old_val = self.env.locals.get(var_name)
            
            for item in iterable_val:
                self.env.locals[var_name] = item
                result = self.eval(node.body)
                if isinstance(result, ast.ReturnStatement): # Handles propagation correctly if returned explicitly
                    pass # Handled differently, we just rely on bubble-up from block
                    
            if old_val is not None:
                self.env.locals[var_name] = old_val
            else:
                if var_name in self.env.locals:
                    del self.env.locals[var_name]
                    
            return None

        elif isinstance(node, ast.IfStatement):
            condition = self.eval(node.condition)
            if condition: # Truthy check
                return self.eval(node.consequence)
            elif node.alternative is not None:
                return self.eval(node.alternative)
            return None

        elif isinstance(node, ast.ReturnStatement):
            return self.eval(node.return_value)

        elif isinstance(node, ast.ExpressionStatement):
            return self.eval(node.expression)

        elif isinstance(node, ast.AssignStatement):
            val = self.eval(node.value)
            if isinstance(node.left, ast.Identifier):
                self.env.set_var(node.left.value, val)
            elif isinstance(node.left, ast.PropAccess):
                # Handle UP.count = 5 
                # Evaluate the base object (e.g. env.axes["UP"])
                base_obj = self.eval(node.left.object)
                if isinstance(base_obj, dict):
                    prop_name = node.left.property.value
                    base_obj[prop_name] = val
                    
        elif isinstance(node, ast.Identifier):
            return self.env.get_var(node.value)

        elif isinstance(node, ast.Literal):
            return node.value

        elif isinstance(node, ast.ArrayLiteral):
            return [self.eval(e) for e in node.elements]
            
        elif isinstance(node, ast.DictLiteral):
            return {k: self.eval(v) for k, v in node.pairs.items()}

        elif isinstance(node, ast.BinaryExpr):
            l = self.eval(node.left)
            r = self.eval(node.right)
            if node.operator == '+': return l + r
            if node.operator == '-': return l - r
            if node.operator == '*': return l * r
            if node.operator == '/': return l / r
            if node.operator == '==': return l == r
            if node.operator == '!=': return l != r
            if node.operator == '>': return l > r
            if node.operator == '<': return l < r

        elif isinstance(node, ast.LambdaExpr):
            # Return the lambda expression node itself for native methods to invoke later
            return node

        elif isinstance(node, ast.PropAccess):
            if isinstance(node.object, ast.Identifier):
                if node.object.value == "SELF":
                    return ("SELF", node.property.value)
                elif node.object.value == "MEMORY":
                    return ("MEMORY", node.property.value)
                elif node.object.value == "OP":
                    return ("OP", node.property.value)
                elif node.object.value == "SIMULATOR":
                    return ("SIMULATOR", node.property.value)
                
            l = self.eval(node.object)
            if isinstance(l, dict):
                return l.get(node.property.value)
            # Check for native methods (e.g., list.APPEND)
            return (l, node.property.value) # Returns tuple (base_object, method_name)

        elif isinstance(node, ast.CallExpr):
            # Could be a user function or native intrinsic
            if isinstance(node.function, ast.PropAccess):
                # E.g. UP.pending.APPEND(task)
                base_info = self.eval(node.function)
                if isinstance(base_info, tuple) and len(base_info) == 2:
                    base_obj, method = base_info
                    
                    if base_obj == "SELF" and method == "save":
                        # SELF.save() -> unparse and write to cross file!
                        from .unparser import JCrossUnparser
                        unparser = JCrossUnparser()
                        raw_data = unparser.unparse_env(self.env, "active_cross")
                        with open(self.file_path, "w", encoding="utf-8") as f:
                            f.write(raw_data)
                        return True
                        
                    if base_obj == "MEMORY" and self.memory_bridge:
                        # Process memory_bridge native arguments dynamically
                        args = [self.eval(a) for a in node.arguments]
                        if method == "query":
                            target = args[0]
                            if isinstance(target, TensionPrimitive):
                                target = target.target_name
                            return self.memory_bridge.query(target)
                        elif method == "get_tensions":
                            return self.memory_bridge.get_tensions()
                        elif method == "inject":
                            priority = args[3] if len(args) > 3 else 0
                            self.memory_bridge.inject(args[0], args[1], args[2], priority)
                            return None
                        elif method == "resolve_tension":
                            return None
                            
                    if base_obj == "OP" and self.memory_bridge:
                        args = [self.eval(a) for a in node.arguments]
                        if method == "UNIFY":
                            self.memory_bridge.inject(args[0], "[同]", args[1], 100.0)
                        elif method == "CHUNK":
                            self.memory_bridge.inject(args[0], "[親]", args[1], 50.0)
                        elif method == "ISOLATE":
                            # Extremely low sequence time effectively hides it
                            self.memory_bridge.inject(args[0], "[絶]", "V_NULL", -9999.0)
                        return None
                        
                    if base_obj == "SIMULATOR":
                        args = [self.eval(a) for a in node.arguments]
                        if method == "run_dynamic":
                            # Dynamic Self-Rewriting JCross parsing evaluation
                            from verantyx.jcross_lang.lexer import Lexer
                            from verantyx.jcross_lang.parser import Parser
                            code_str = str(args[0])
                            lexer = Lexer(code_str)
                            parser = Parser(lexer)
                            program = parser.parse_program()
                            if program:
                                return self.eval(program)
                            return None
                    # or handle Lambdas natively!
                    args = []
                    for a in node.arguments:
                        val = self.eval(a)
                        args.append(val)
                    
                    if method == "APPEND" and isinstance(base_obj, list):
                        base_obj.append(args[0])
                        return None
                    elif method == "REMOVE" and isinstance(base_obj, list):
                        if args[0] in base_obj:
                            base_obj.remove(args[0])
                        return None
                    elif method == "EXTEND" and isinstance(base_obj, list):
                        base_obj.extend(args[0])
                        return None
                    elif method == "ELEVATE" and isinstance(base_obj, dict):
                        base_obj["time_idx"] = base_obj.get("time_idx", 0.0) + float(args[0])
                        return None
                    elif method == "DECAY" and isinstance(base_obj, dict):
                        base_obj["time_idx"] = base_obj.get("time_idx", 0.0) - float(args[0])
                        return None
                    elif method == "MAP" and isinstance(base_obj, list):
                        lambda_node = args[0]
                        if isinstance(lambda_node, ast.LambdaExpr):
                            var_name = lambda_node.params[0].value
                            mapped = []
                            old_val = self.env.locals.get(var_name)
                            for item in base_obj:
                                self.env.locals[var_name] = item
                                mapped.append(self.eval(lambda_node.body))
                            if old_val is not None: self.env.locals[var_name] = old_val
                            else: self.env.locals.pop(var_name, None)
                            return mapped
                    elif method == "FILTER" and isinstance(base_obj, list):
                        lambda_node = args[0]
                        if isinstance(lambda_node, ast.LambdaExpr):
                            var_name = lambda_node.params[0].value
                            filtered = []
                            old_val = self.env.locals.get(var_name)
                            for item in base_obj:
                                self.env.locals[var_name] = item
                                if self.eval(lambda_node.body):
                                    filtered.append(item)
                            if old_val is not None: self.env.locals[var_name] = old_val
                            else: self.env.locals.pop(var_name, None)
                            return filtered
                    elif method == "REDUCE" and isinstance(base_obj, list):
                        # Not implementing reduce correctly yet.
                        pass
                    
            elif isinstance(node.function, ast.Identifier):
                func = self.env.get_var(node.function.value)
                if isinstance(func, (ast.FuncDef, ast.PatternDef)):
                    args = [self.eval(a) for a in node.arguments]
                    
                    # Create highly isolated scope locals for function invocation
                    old_locals = self.env.locals
                    self.env.locals = {param.value: arg for param, arg in zip(func.params, args)}
                    
                    try:
                        return self.eval(func.body)
                    finally:
                        self.env.locals = old_locals

    def run_function(self, func_name: str, *args):
        # Native Python entry point to trigger a .jcross function
        func_node = self.env.functions.get(func_name)
        if not func_node:
            raise KeyError(f"Function {func_name} not found")
            
        old_locals = self.env.locals
        self.env.locals = {param.value: arg for param, arg in zip(func_node.params, args)}
        
        try:
            return self.eval(func_node.body)
        finally:
            self.env.locals = old_locals
