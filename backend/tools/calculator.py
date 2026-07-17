"""数学计算工具"""
import ast
import math
import operator
from typing import Union

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool


# Define allowed operators for safe evaluation
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Define allowed math functions
ALLOWED_MATH_FUNCTIONS = {
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
    'exp': math.exp,
    'pi': math.pi,
    'e': math.e,
}


def safe_eval(expression: str) -> Union[float, int]:
    """
    Safely evaluate a mathematical expression using AST parsing.
    Only allows basic math operations and predefined functions.
    """
    # Parse expression to AST
    tree = ast.parse(expression, mode='eval')
    
    def evaluate(node):
        """Recursively evaluate AST nodes."""
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in ALLOWED_OPERATORS:
                raise ValueError(f"不支持的运算符：{type(node.op).__name__}")
            left = evaluate(node.left)
            right = evaluate(node.right)
            return ALLOWED_OPERATORS[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in ALLOWED_OPERATORS:
                raise ValueError(f"不支持的运算符：{type(node.op).__name__}")
            operand = evaluate(node.operand)
            return ALLOWED_OPERATORS[type(node.op)](operand)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("只允许调用简单的数学函数")
            func_name = node.func.id
            if func_name not in ALLOWED_MATH_FUNCTIONS:
                raise ValueError(f"不支持的函数：{func_name}")
            args = [evaluate(arg) for arg in node.args]
            return ALLOWED_MATH_FUNCTIONS[func_name](*args)
        elif isinstance(node, ast.Name):
            if node.id in ALLOWED_MATH_FUNCTIONS:
                return ALLOWED_MATH_FUNCTIONS[node.id]
            raise ValueError(f"未定义的变量：{node.id}")
        else:
            raise ValueError(f"不支持的表达式类型：{type(node).__name__}")
    
    return evaluate(tree.body)


@tool("calculate")
def calculate(expression: str) -> str:
    """
    Safely evaluate mathematical expressions.
    Supports basic operations (+, -, *, /, %, **) and common math functions (sqrt, sin, cos, tan, log, exp, etc.).
    Use this tool when users need precise mathematical calculations.
    
    Args:
        expression: Mathematical expression to evaluate (e.g., '2 + 3 * 4', 'sqrt(16)', 'sin(pi/2)').
    
    Returns:
        Result of the calculation or error message.
    """
    try:
        # Clean expression
        expression = expression.strip()
        
        # Validate expression is not empty
        if not expression:
            return "错误：表达式不能为空"
        
        # Evaluate safely
        result = safe_eval(expression)
        
        # Format result
        if isinstance(result, float):
            # Check if it's actually an integer
            if result.is_integer():
                result = int(result)
            else:
                # Round to reasonable precision
                result = round(result, 10)
        
        return f"计算结果：{expression} = {result}"
        
    except ValueError as e:
        return f"计算错误：{str(e)}"
    except SyntaxError:
        return "错误：表达式语法不正确"
    except ZeroDivisionError:
        return "错误：除数不能为零"
    except Exception as e:
        return f"计算失败：{str(e)}"