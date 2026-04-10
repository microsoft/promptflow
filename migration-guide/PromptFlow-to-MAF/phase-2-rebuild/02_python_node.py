"""
Migrates a Prompt Flow Python code node.

In MAF, custom logic lives directly inside a @handler method — no separate
YAML snippet, no per-node file registration required.

Prompt Flow equivalent:
    def clean_text(text: str) -> str:
        return text.strip().upper()
"""

import asyncio

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

load_dotenv()


class TextCleanerExecutor(Executor):
    """Replaces the Prompt Flow Python node.

    Any Python logic — library calls, data transforms, API calls — goes
    inside the @handler method. WorkflowContext[str] sends the result downstream.
    """

    @handler
    async def clean(self, text: str, ctx: WorkflowContext[str]) -> None:
        cleaned = text.strip().upper()
        await ctx.send_message(cleaned)


class OutputExecutor(Executor):
    """Terminal executor — yields the final workflow output."""

    @handler
    async def output(self, text: str, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(text)


workflow = (
    WorkflowBuilder(name="PythonNodeWorkflow")
    .register_executor(lambda: TextCleanerExecutor(id="cleaner"), name="Cleaner")
    .register_executor(lambda: OutputExecutor(id="output"), name="Output")
    .add_edge("Cleaner", "Output")
    .set_start_executor("Cleaner")
    .build()
)


async def main():
    result = await workflow.run("  hello from prompt flow  ")
    print(result.get_outputs()[0])  # → "HELLO FROM PROMPT FLOW"


if __name__ == "__main__":
    asyncio.run(main())
