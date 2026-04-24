"""
Per-row MAF workflow for eval-basic.

Converts the `line_process` node from the original PromptFlow evaluation flow.
Each workflow invocation processes a single (groundtruth, prediction) pair and
yields "Correct" or "Incorrect".

Original flow graph (per-row nodes only):
    [inputs: groundtruth, prediction] → [line_process] → output
"""

import asyncio
from dataclasses import dataclass

from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


@dataclass
class EvalInput:
    groundtruth: str
    prediction: str


class LineProcessExecutor(Executor):
    """Replaces the `line_process` Python node.

    Compares groundtruth and prediction (case-insensitive) and yields the result.
    """

    @handler
    async def process(self, input: EvalInput, ctx: WorkflowContext[Never, str]) -> None:
        result = "Correct" if input.groundtruth.lower() == input.prediction.lower() else "Incorrect"
        await ctx.yield_output(result)


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each batch row
    needs its own workflow instance.
    """
    _line_process = LineProcessExecutor(id="line_process")
    return WorkflowBuilder(name="EvalBasicRow", start_executor=_line_process).build()


async def main():
    """Quick smoke test with a single row."""
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="sunny", prediction="Sunny"))
    print(result.get_outputs()[0])  # → "Correct"


if __name__ == "__main__":
    asyncio.run(main())
