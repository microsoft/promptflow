"""
Migrates Prompt Flow parallel nodes — two nodes with no shared dependencies
that both feed into a merge/aggregate node.

In MAF:
  - add_fan_out_edges() broadcasts one message to multiple executors concurrently
  - add_fan_in_edges() waits for ALL upstream executors before proceeding

Prompt Flow equivalent:
    [Dispatch] --> [NodeA] (no deps) --> [Merge]
               --> [NodeB] (no deps) --> [Merge]
"""

import asyncio

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

load_dotenv()


class DispatchExecutor(Executor):
    """Entry point — broadcasts the input to both parallel paths."""

    @handler
    async def dispatch(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text)


class PathAExecutor(Executor):
    """First parallel branch. Replace with your actual processing logic."""

    @handler
    async def process_a(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(f"PathA: {text.upper()}")


class PathBExecutor(Executor):
    """Second parallel branch. Replace with your actual processing logic."""

    @handler
    async def process_b(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(f"PathB: {text[::-1]}")


class AggregatorExecutor(Executor):
    """Merge node — runs only after both PathA and PathB have completed.

    fan-in delivers all upstream results as list[str].
    The order of results matches the order executors were declared in
    add_fan_in_edges() — [PathA_result, PathB_result] — so it is safe to
    rely on positional indexing if needed.
    """

    @handler
    async def aggregate(self, results: list[str], ctx: WorkflowContext[Never, str]) -> None:
        combined = " | ".join(results)
        await ctx.yield_output(combined)


_dispatch = DispatchExecutor(id="dispatch")
_path_a = PathAExecutor(id="path_a")
_path_b = PathBExecutor(id="path_b")
_aggregate = AggregatorExecutor(id="aggregate")

workflow = (
    WorkflowBuilder(name="ParallelWorkflow", start_executor=_dispatch)
    .add_fan_out_edges(_dispatch, [_path_a, _path_b])
    .add_fan_in_edges([_path_a, _path_b], _aggregate)
    .build()
)


async def main():
    result = await workflow.run("hello")
    print(result.get_outputs()[0])  # → "PathA: HELLO | PathB: olleh" (order matches add_fan_in_edges declaration)


if __name__ == "__main__":
    asyncio.run(main())
