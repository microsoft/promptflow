"""
Alternative client for teams using Azure AI Foundry as their model hub.

NOTE: This file demonstrates a **standalone agent test** — it uses Agent
directly without the Executor + WorkflowBuilder pattern. This is intentional
for quickly verifying Foundry connectivity. For production workflows, see the
samples in phase-2-rebuild/ which show the full Executor/WorkflowBuilder
pattern.

Use FoundryChatClient (from agent_framework.foundry) when connecting to a
Foundry project endpoint. AzureOpenAIChatClient is for raw Azure OpenAI
Service endpoints and should not be used here.

Prerequisites:
    pip install agent-framework-foundry azure-identity
    Set in .env: FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL
"""

import asyncio
import os

from dotenv import load_dotenv
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

load_dotenv()

# Endpoint format: https://<resource>.services.ai.azure.com
client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["FOUNDRY_MODEL"],
    credential=DefaultAzureCredential(),
)

agent = Agent(
    client=client,
    name="DocQAAgent",
    instructions="You are a precise document Q&A assistant.",
)


async def main():
    result = await agent.run("What is the refund policy?")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
