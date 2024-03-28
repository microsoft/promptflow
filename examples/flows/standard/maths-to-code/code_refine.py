from promptflow.core import tool
import ast
import json


def infinite_loop_check(code_snippet):
    tree = ast.parse(code_snippet)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if not node.orelse:
                return True
    return False


def syntax_error_check(code_snippet):
    try:
        ast.parse(code_snippet)
    except SyntaxError:
        return True
    return False


def error_fix(code_snippet):
    tree = ast.parse(code_snippet)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if not node.orelse:
                node.orelse = [ast.Pass()]
    return ast.unparse(tree)


@tool
def code_refine(original_code: str) -> str:

    try:
        original_code = json.loads(original_code)["code"]
        fixed_code = None

        if infinite_loop_check(original_code):
            fixed_code = error_fix(original_code)
        else:
            fixed_code = original_code

        if syntax_error_check(fixed_code):
            fixed_code = error_fix(fixed_code)

        return fixed_code
    except json.JSONDecodeError:
        return "JSONDecodeError"
    except Exception as e:
        return "Unknown Error:" + str(e)


if __name__ == "__main__":
    code = "{\n    \"code\": \"distance_A = 10 * 0.5\\ndistance_B = 15 * t\\n\\n\
        equation: distance_A = distance_B\\n\\n\10 * 0.5 = 15 * t\\n\\nt = (10 * 0.5) / 15\\n\\nprint(t)\"\n}"
    code_refine = code_refine(code)
    print(code_refine)
