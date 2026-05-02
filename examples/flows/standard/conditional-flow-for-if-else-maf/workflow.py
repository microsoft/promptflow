import asyncio
import random
from dataclasses import dataclass

from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


@dataclass
class SafetyResult:
    question: str
    is_safe: bool


class ContentSafetyExecutor(Executor):
    @handler
    async def check(self, question: str, ctx: WorkflowContext[SafetyResult]) -> None:
        # Placeholder: replace with a real content safety check.
        is_safe = random.choice([True, False])
        await ctx.send_message(SafetyResult(question=question, is_safe=is_safe))


class LLMResultExecutor(Executor):
    @handler
    async def run_llm(self, msg: SafetyResult, ctx: WorkflowContext[Never, str]) -> None:
        # Placeholder: replace with a real LLM call.
        answer = (
            "Prompt flow is a suite of development tools designed to streamline "
            "the end-to-end development cycle of LLM-based AI applications."
        )
        await ctx.yield_output(answer)


class DefaultResultExecutor(Executor):
    @handler
    async def default(self, msg: SafetyResult, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(f"I'm not familiar with your query: {msg.question}.")


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _safety = ContentSafetyExecutor(id="content_safety_check")
    _llm = LLMResultExecutor(id="llm_result")
    _default = DefaultResultExecutor(id="default_result")
    return (
        WorkflowBuilder(name="ConditionalIfElseWorkflow", start_executor=_safety)
        .add_edge(_safety, _llm, condition=lambda msg: msg.is_safe)
        .add_edge(_safety, _default, condition=lambda msg: not msg.is_safe)
        .build()
    )


async def main():
    workflow = create_workflow()
    result = await workflow.run("What is Prompt flow?")
    print(f"Answer: {result.get_outputs()[0]}")


if __name__ == "__main__":
    asyncio.run(main())
