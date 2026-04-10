"""
Migrates a Prompt Flow custom tool node or tool integration.

In MAF, Python functions are registered as agent tools by passing them to
tools=[] on the agent. The agent calls them autonomously during a run based
on its instructions and the user input.

Prompt Flow equivalent:
    [LLM node] --> [Python tool node] (e.g. a custom API call or lookup)
"""

import asyncio

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.azure import AzureOpenAIChatClient

load_dotenv()


# --- Tool functions ----------------------------------------------------------
# These replace Prompt Flow Python tool nodes.
# Any plain Python function can be passed to tools=[].
# The docstring is used by the agent to decide when and how to call the function.

def get_order_status(order_id: str) -> str:
    """Look up the status of a customer order by order ID.

    Args:
        order_id: The unique order identifier.

    Returns:
        A string describing the current order status.
    """
    # Replace with your real data source (database, API call, etc.)
    mock_orders = {
        "ORD-001": "Shipped — expected delivery 9 Apr 2026",
        "ORD-002": "Processing — not yet dispatched",
        "ORD-003": "Delivered — 3 Apr 2026",
    }
    return mock_orders.get(order_id, f"Order {order_id} not found.")


def get_refund_policy() -> str:
    """Return the company refund policy.

    Returns:
        A string describing the refund policy.
    """
    return "Refunds are accepted within 30 days of purchase with proof of receipt."


# --- Executor ----------------------------------------------------------------

class ToolAgentExecutor(Executor):
    """Replaces an LLM node wired to one or more Python tool nodes.

    The agent decides autonomously which tools to call based on the user
    question and its instructions. tools=[] accepts plain Python callables.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = AzureOpenAIChatClient().as_agent(
            name="SupportAgent",
            instructions=(
                "You are a customer support assistant. "
                "Use the available tools to answer questions about orders and refunds. "
                "Always use a tool if the answer can be looked up — do not guess."
            ),
            tools=[get_order_status, get_refund_policy],
        )

    @handler
    async def run(self, question: str, ctx: WorkflowContext[Never, str]) -> None:
        result = await self._agent.run(question)
        await ctx.yield_output(result)


workflow = (
    WorkflowBuilder(name="FunctionToolsWorkflow")
    .register_executor(lambda: ToolAgentExecutor(id="tool_agent"), name="ToolAgent")
    .set_start_executor("ToolAgent")
    .build()
)


async def main():
    questions = [
        "What is the status of order ORD-002?",
        "Can I get a refund on something I bought 2 weeks ago?",
    ]
    for q in questions:
        result = await workflow.run(q)
        print(f"Q: {q}")
        print(f"A: {result.get_outputs()[0]}\n")


if __name__ == "__main__":
    asyncio.run(main())
