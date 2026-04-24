import ast
import asyncio
import logging
import os
from typing import List

import tiktoken
from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient, OpenAIChatOptions

from divider import Divider
from file import File
from prompt import PromptLimitException, docstring_prompt

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers (extracted from original generate_docstring_tool.py / azure_open_ai.py)
# ---------------------------------------------------------------------------


def get_imports(content: str) -> List[str]:
    tree = ast.parse(content)
    import_statements = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                import_statements.append(f"import {n.name}")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            for n in node.names:
                import_statements.append(f"from {module_name} import {n.name}")
    return import_statements


_TOKEN_BUDGET = {
    "gpt-4-32k": 31000,
    "gpt-4": 7000,
    "gpt-3.5-turbo-16k": 15000,
}
_DEFAULT_BUDGET = 4000


def _count_tokens(text: str, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(text))


def _get_message_tokens(messages: List[dict], model: str) -> int:
    num_tokens = 0
    for message in messages:
        num_tokens += 5
        for key, value in message.items():
            if value:
                num_tokens += _count_tokens(value, model)
            if key == "name":
                num_tokens += 5
    num_tokens += 5  # assistant priming
    return num_tokens


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = "You are a Python engineer."


class LoadCodeExecutor(Executor):
    @handler
    async def load(self, source: str, ctx: WorkflowContext[str]) -> None:
        file = File(source)
        await ctx.send_message(file.content)


class DivideCodeExecutor(Executor):
    @handler
    async def divide(self, file_content: str, ctx: WorkflowContext[list]) -> None:
        divided = Divider.divide_file(file_content)
        await ctx.send_message(divided)


class GenerateDocstringExecutor(Executor):
    """Generates docstrings for each code part using the LLM, then combines.

    Collapses the original ``generate_docstring`` + ``combine_code`` nodes.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = None  # lazily initialised on first use

    def _ensure_agent(self) -> None:
        if self._agent is not None:
            return
        self._model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")
        self._max_tokens = int(os.environ.get("MAX_TOKENS", "1200"))
        total = _TOKEN_BUDGET.get(self._model, _DEFAULT_BUDGET)
        self._tokens_limit = total - self._max_tokens

        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=self._model,
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="DocstringAgent",
            instructions=SYSTEM_PROMPT,
        )

    # -- token helpers -------------------------------------------------------

    def _validate_tokens(self, prompt_text: str) -> None:
        self._ensure_agent()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ]
        total = _get_message_tokens(messages, self._model)
        if total > self._tokens_limit:
            raise PromptLimitException(
                f"token count {total} exceeds limit {self._tokens_limit}"
            )

    # -- LLM call ------------------------------------------------------------

    async def _generate_one(self, prompt_text: str) -> str:
        self._ensure_agent()
        response = await self._agent.run(
            prompt_text,
            options=OpenAIChatOptions(temperature=0.1, max_tokens=self._max_tokens),
        )
        return response.text

    # -- handler -------------------------------------------------------------

    @handler
    async def generate(self, divided: list, ctx: WorkflowContext[Never, str]) -> None:
        self._ensure_agent()
        divided = list(reversed(divided))
        all_divided: List[str] = []

        # If too many imports result in tokens exceeding the limit, please set an empty string.
        modules = ''  # '\n'.join(get_imports(divided[-1]))
        modules_tokens = _count_tokens(modules, self._model)
        if modules_tokens > 300:
            logging.warning(f'Too many imports, the number of tokens is {modules_tokens}')
        if modules_tokens > 500:
            logging.warning(
                f'Too many imports, the number of tokens is {modules_tokens}, will set an empty string.'
            )
            modules = ''

        # Divide the code into two parts if the global class/function is too long.
        while len(divided):
            item = divided.pop()
            try:
                self._validate_tokens(docstring_prompt(code=item, module=modules))
            except PromptLimitException as e:
                logging.warning(e.message + ', will divide the code into two parts.')
                divided_tmp = Divider.divide_half(item)
                if len(divided_tmp) > 1:
                    divided.extend(list(reversed(divided_tmp)))
                    continue
            except Exception as e:
                logging.warning(e)
            all_divided.append(item)

        # Generate docstrings concurrently
        tasks = []
        last_code = ''
        for item in all_divided:
            if Divider.has_class_or_func(item):
                tasks.append(
                    self._generate_one(docstring_prompt(last_code=last_code, code=item, module=modules))
                )
            else:
                # No class/function — nothing to generate.
                tasks.append(asyncio.sleep(0))
            last_code = item

        res_doc = await asyncio.gather(*tasks)

        new_code: List[str] = []
        for i in range(len(all_divided)):
            if isinstance(res_doc[i], str):
                new_code.append(Divider.merge_doc2code(res_doc[i], all_divided[i]))
            else:
                new_code.append(all_divided[i])

        # Combine (collapsed from the combine_code prompt node)
        result = ''.join(new_code)
        await ctx.yield_output(result)


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

def create_workflow():
    """Factory that builds a fresh workflow instance (safe for concurrent use)."""
    _load = LoadCodeExecutor(id="load_code")
    _divide = DivideCodeExecutor(id="divide_code")
    _generate = GenerateDocstringExecutor(id="generate_docstring")

    return (
        WorkflowBuilder(name="GenDocstringWorkflow", start_executor=_load)
        .add_edge(_load, _divide)
        .add_edge(_divide, _generate)
        .build()
    )


workflow = create_workflow()
