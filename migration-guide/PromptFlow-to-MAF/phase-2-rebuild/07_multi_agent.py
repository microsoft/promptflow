"""
Migrates a multi-step Prompt Flow that requires specialist handling based
on the nature of the input — implemented in MAF as a multi-agent handoff.

A triage agent classifies the input and routes it to one of two specialist
agents based on the classification result.

Prompt Flow equivalent:
    [Classify node] --> [SpecialistA LLM node]  (if billing)
                    --> [SpecialistB LLM node]  (if technical)
"""

import asyncio

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.azure import AzureOpenAIChatClient

load_dotenv()

# One shared client is the recommended production pattern — instantiating a
# separate client per agent is unnecessary and wastes connection resources.
_client = AzureOpenAIChatClient()

triage_agent = _client.as_agent(
    name="TriageAgent",
    instructions=(
        "You are a triage assistant. Classify the user message as either "
        "'billing' or 'technical'. Reply with exactly one word: billing or technical."
    ),
)

billing_agent = _client.as_agent(
    name="BillingAgent",
    instructions=(
        "You are a billing support specialist. "
        "Answer questions about invoices, payments, and subscriptions concisely."
    ),
)

technical_agent = _client.as_agent(
    name="TechnicalAgent",
    instructions=(
        "You are a technical support specialist. "
        "Answer questions about product features, errors, and configuration concisely."
    ),
)


# --- Executors ---------------------------------------------------------------

class TriageExecutor(Executor):
    """Classifies the input and forwards a tagged message downstream.

    The message format is '<category>||<original question>' so that
    downstream executors can extract both the routing label and the question.
    WorkflowContext[str] sends the tagged string to the next executor.
    """

    @handler
    async def triage(self, question: str, ctx: WorkflowContext[str]) -> None:
        result = await triage_agent.run(question)
        category = result.strip().lower()
        if category not in ("billing", "technical"):
            print(f"[TriageExecutor] Unexpected category '{category}'; defaulting to 'technical'.", flush=True)
            category = "technical"  # default fallback
        await ctx.send_message(f"{category}||{question}")


class BillingExecutor(Executor):
    """Handles billing queries. Only receives messages routed via is_billing()."""

    @handler
    async def handle(self, tagged: str, ctx: WorkflowContext[Never, str]) -> None:
        _, question = tagged.split("||", 1)
        result = await billing_agent.run(question)
        await ctx.yield_output(result)


class TechnicalExecutor(Executor):
    """Handles technical queries. Only receives messages routed via is_technical()."""

    @handler
    async def handle(self, tagged: str, ctx: WorkflowContext[Never, str]) -> None:
        _, question = tagged.split("||", 1)
        result = await technical_agent.run(question)
        await ctx.yield_output(result)


# --- Condition functions -----------------------------------------------------

def is_billing(message: str) -> bool:
    return message.startswith("billing||")


def is_technical(message: str) -> bool:
    return message.startswith("technical||")


# --- Workflow ----------------------------------------------------------------

workflow = (
    WorkflowBuilder(name="MultiAgentHandoffWorkflow")
    .register_executor(lambda: TriageExecutor(id="triage"), name="Triage")
    .register_executor(lambda: BillingExecutor(id="billing"), name="Billing")
    .register_executor(lambda: TechnicalExecutor(id="technical"), name="Technical")
    .add_edge("Triage", "Billing", condition=is_billing)
    .add_edge("Triage", "Technical", condition=is_technical)
    .set_start_executor("Triage")
    .build()
)


async def main():
    questions = [
        "My invoice from last month looks wrong.",
        "The app keeps crashing when I open the settings page.",
    ]
    for q in questions:
        result = await workflow.run(q)
        print(f"Q: {q}")
        print(f"A: {result.get_outputs()[0]}\n")


if __name__ == "__main__":
    asyncio.run(main())
