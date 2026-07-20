import ast
import operator
import math

def calculate(expression: str) -> str:
    """
    Evaluates a mathematical expression and returns the result.
    Use this tool when you need to perform calculations.
    """
    # Allowed operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # Allowed math functions and constants
    functions = {
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'sqrt': math.sqrt,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'pi': math.pi,
        'e': math.e,
        'abs': abs,
        'round': round
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            if type(node.op) in operators:
                return operators[type(node.op)](left, right)
            raise ValueError(f"Unsupported operator: {type(node.op)}")
        elif isinstance(node, ast.UnaryOp):
            operand = eval_node(node.operand)
            if type(node.op) in operators:
                return operators[type(node.op)](operand)
            raise ValueError(f"Unsupported unary operator: {type(node.op)}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in functions and callable(functions[func_name]):
                    args = [eval_node(arg) for arg in node.args]
                    return functions[func_name](*args)
                raise ValueError(f"Unsupported function: {func_name}")
            raise ValueError("Only standard math functions are supported.")
        elif isinstance(node, ast.Name):
            if node.id in functions and not callable(functions[node.id]):
                return functions[node.id]
            raise ValueError(f"Unsupported variable: {node.id}")
        elif isinstance(node, ast.Expression):
            return eval_node(node.body)
        else:
            raise ValueError(f"Unsupported syntax: {type(node)}")

    try:
        # Parse the expression into an AST
        node = ast.parse(expression, mode='eval')
        result = eval_node(node)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"
