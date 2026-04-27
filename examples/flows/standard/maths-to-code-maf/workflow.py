import ast
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from io import StringIO

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

_MATH_EXAMPLES = [
    {
        "question": "What is 37593 * 67?",
        "code": '{\n    "code": "print(37593 * 67)"\n}',
    },
    {
        "question": "What is the value of x in the equation 2x + 3 = 11?",
        "code": '{\n    "code": "print((11-3)/2)"\n}',
    },
    {
        "question": "How many of the integers between 0 and 99 inclusive are divisible by 8?",
        "code": '{\n    "code": "count = 0\\nfor i in range(100):\\n    '
        'if i % 8 == 0:\\n        count += 1\\nprint(count)"\n}',
    },
]

_SYSTEM_PROMPT = (
    "I want you to act as a Math expert specializing in Algebra, Geometry, and Calculus. "
    "Given the question, develop python code to model the user's question.\n"
    "The python code will print the result at the end.\n"
    "Please generate executable python code, your reply will be in JSON format, something like:\n"
    '{\n    "code": "print(1+1)"\n}'
)

_USER_TEMPLATE = """\
This a set of examples including question and the final answer:
{examples}

Now come to the real task, make sure return a valid json. The json should \
contain a key named "code" and the value is the python code. For example:
{{
    "code": "print(1+1)"
}}
QUESTION: {question}
CODE:"""


def _format_examples() -> str:
    parts = []
    for ex in _MATH_EXAMPLES:
        parts.append(f"QUESTION: {ex['question']}\nCODE:\n{ex['code']}\n")
    return "\n".join(parts)


def _infinite_loop_check(code_snippet):
    tree = ast.parse(code_snippet)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if not node.orelse:
                return True
    return False


def _syntax_error_check(code_snippet):
    try:
        ast.parse(code_snippet)
    except SyntaxError:
        return True
    return False


def _error_fix(code_snippet):
    tree = ast.parse(code_snippet)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if not node.orelse:
                node.orelse = [ast.Pass()]
    return ast.unparse(tree)


@dataclass
class MathResult:
    code: str
    answer: str


class CodeGenExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="MathCodeGen",
            instructions=_SYSTEM_PROMPT,
        )

    @handler
    async def generate(self, question: str, ctx: WorkflowContext[str]) -> None:
        user_msg = _USER_TEMPLATE.format(
            examples=_format_examples(), question=question
        )
        response = await self._agent.run(user_msg)
        await ctx.send_message(response.text)


class CodeRefineExecutor(Executor):
    @handler
    async def refine(self, original_code: str, ctx: WorkflowContext[str]) -> None:
        try:
            code = json.loads(original_code)["code"]
            fixed = code
            if _infinite_loop_check(code):
                fixed = _error_fix(code)
            if _syntax_error_check(fixed):
                fixed = _error_fix(fixed)
            await ctx.send_message(fixed)
        except json.JSONDecodeError:
            await ctx.send_message("JSONDecodeError")
        except Exception as e:
            await ctx.send_message("Unknown Error:" + str(e))


class CodeExecutionExecutor(Executor):
    @handler
    async def run_code(self, code_snippet: str, ctx: WorkflowContext[Never, MathResult]) -> None:
        if code_snippet == "JSONDecodeError" or code_snippet.startswith("Unknown Error:"):
            await ctx.yield_output(MathResult(code=code_snippet, answer=code_snippet))
            return

        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()
        try:
            exec(code_snippet.lstrip())  # noqa: S102
        except Exception as e:
            sys.stdout = old_stdout
            await ctx.yield_output(MathResult(code=code_snippet, answer=str(e)))
            return

        sys.stdout = old_stdout
        answer = redirected_output.getvalue().strip()
        await ctx.yield_output(MathResult(code=code_snippet, answer=answer))


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _code_gen = CodeGenExecutor(id="code_gen")
    _code_refine = CodeRefineExecutor(id="code_refine")
    _code_exec = CodeExecutionExecutor(id="final_code_execution")
    return (
        WorkflowBuilder(name="MathsToCodeWorkflow", start_executor=_code_gen)
        .add_edge(_code_gen, _code_refine)
        .add_edge(_code_refine, _code_exec)
        .build()
    )


async def main():
    workflow = create_workflow()
    result = await workflow.run(
        "If a rectangle has a length of 10 and width of 5, what is the area?"
    )
    output = result.get_outputs()[0]
    print(f"Code: {output.code}")
    print(f"Answer: {output.answer}")


if __name__ == "__main__":
    asyncio.run(main())
