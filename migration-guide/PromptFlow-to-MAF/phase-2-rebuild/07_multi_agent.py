"""
Migrates a multi-step Prompt Flow that requires specialist handling based
on the nature of the input — implemented in MAF as a multi-agent handoff
using the HandoffBuilder from agent-framework-orchestrations.

A triage agent classifies the input and uses tool-based handoffs to route
to specialist agents. The HandoffBuilder automatically generates handoff
tools for each participant.

Prompt Flow equivalent:
    [Classify node] --> [SpecialistA LLM node]  (if billing)
                    --> [SpecialistB LLM node]  (if technical)

Prerequisites:
    pip install agent-framework-orchestrations --pre
    Set in .env: FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL
"""

import asyncio
import os

from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity import DefaultAzureCredential

load_dotenv()

# One shared client is the recommended production pattern — instantiating a
# separate client per agent is unnecessary and wastes connection resources.
_client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["FOUNDRY_MODEL"],
    credential=DefaultAzureCredential(),
)

triage_agent = Agent(
    client=_client,
    name="triage_agent",
    instructions=(
        "You are frontline support triage. Route customer issues to the "
        "appropriate specialist agent based on the problem described. "
        "Use the handoff tools to transfer to billing_agent or technical_agent."
    ),
)

billing_agent = Agent(
    client=_client,
    name="billing_agent",
    instructions=(
        "You are a billing support specialist. "
        "Answer questions about invoices, payments, and subscriptions concisely."
    ),
)

technical_agent = Agent(
    client=_client,
    name="technical_agent",
    instructions=(
        "You are a technical support specialist. "
        "Answer questions about product features, errors, and configuration concisely."
    ),
)

# HandoffBuilder automatically creates handoff tools for each participant,
# allowing agents to transfer control by invoking a tool call (e.g.
# handoff_to_billing_agent). This replaces the manual tagged-string
# routing pattern with condition functions.
workflow = (
    HandoffBuilder(
        name="MultiAgentHandoffWorkflow",
        participants=[triage_agent, billing_agent, technical_agent],
        # Stop when a specialist has responded (conversation has > 2 messages
        # and the last message is not from triage).
        termination_condition=lambda conversation: (
            len(conversation) > 2
            and conversation[-1].author_name != "triage_agent"
        ),
    )
    .with_start_agent(triage_agent)
    .build()
)


async def main():
    questions = [
        "My invoice from last month looks wrong.",
        "The app keeps crashing when I open the settings page.",
    ]
    for q in questions:
        result = await workflow.run(q)
        outputs = result.get_outputs()
        print(f"Q: {q}")
        if outputs:
            # The handoff workflow yields the full conversation as output.
            # The last message is typically the specialist's response.
            conversation = outputs[0]
            if isinstance(conversation, list) and conversation:
                last_msg = conversation[-1]
                speaker = getattr(last_msg, "author_name", None) or "assistant"
                print(f"A ({speaker}): {last_msg.text}\n")
            else:
                print(f"A: {conversation}\n")


if __name__ == "__main__":
    asyncio.run(main())
