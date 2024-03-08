from openai import AzureOpenAI
from promptflow.tracing import trace, start_trace
import ast
import os


@trace
def infinite_loop_check(code_snippet):
    tree = ast.parse(code_snippet)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if not node.orelse:
                return True
    return False


@trace
def syntax_error_check(code_snippet):
    try:
        ast.parse(code_snippet)
    except SyntaxError:
        return True
    return False


@trace
def error_fix(code_snippet):
    tree = ast.parse(code_snippet)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if not node.orelse:
                node.orelse = [ast.Pass()]
    return ast.unparse(tree)


@trace
def code_refine(original_code: str) -> str:
    original_code = original_code.replace("python", "").replace("`", "").strip()
    fixed_code = None

    if infinite_loop_check(original_code):
        fixed_code = error_fix(original_code)
    else:
        fixed_code = original_code

    if syntax_error_check(fixed_code):
        fixed_code = error_fix(fixed_code)

    return fixed_code


@trace
def code_gen(client: AzureOpenAI, question: str) -> str:
    sys_prompt = (
        "I want you to act as a Math expert specializing in Algebra, Geometry, and Calculus. "
        "Given the question, develop python code to model the user's question. "
        "Make sure only reply the executable code, no other words."
    )
    completion = client.chat.completions.create(
        model="my-dep",
        messages=[
            {
                "role": "system",
                "content": sys_prompt,
            },
            {"role": "user", "content": question},
        ],
    )
    raw_code = completion.choices[0].message.content
    return code_refine(raw_code)


if __name__ == "__main__":
    start_trace()

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2023-12-01-preview",
    )

    question = "What is 37593 * 67?"

    code = code_gen(client, question)
    print(code)
