"""
Migrates a Prompt Flow RAG pipeline.

AzureAISearchContextProvider replaces all three PF RAG nodes — it handles
embedding generation and vector similarity search automatically before
every agent.run() call.

Prompt Flow equivalent (3 separate nodes):
    [Embed Text] --> [Vector DB Lookup] --> [LLM node]

Prerequisites:
    pip install agent-framework-azure-ai-search agent-framework-foundry azure-identity
    Set in .env: FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL,
                 AZURE_AI_SEARCH_ENDPOINT, AZURE_AI_SEARCH_INDEX_NAME,
                 AZURE_AI_SEARCH_API_KEY
"""

import asyncio
import os

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.foundry import FoundryChatClient
from agent_framework_azure_ai_search import AzureAISearchContextProvider
from azure.identity import DefaultAzureCredential

load_dotenv()


# Replaces: Embed Text node + Vector DB Lookup node.
# Queries Azure AI Search and injects retrieved documents into the agent's
# context automatically before every agent.run() call.
search_provider = AzureAISearchContextProvider(
    endpoint=os.environ["AZURE_AI_SEARCH_ENDPOINT"],
    index_name=os.environ["AZURE_AI_SEARCH_INDEX_NAME"],
    api_key=os.environ["AZURE_AI_SEARCH_API_KEY"],
)


class RAGExecutor(Executor):
    """Replaces the Embed Text, Vector DB Lookup, and LLM nodes combined.

    Attaching context_providers=[search_provider] means retrieval runs
    automatically — no separate executor needed for embedding or search.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL"],
            credential=DefaultAzureCredential(),
        )
        self._agent = Agent(
            client=client,
            name="DocQAAgent",
            instructions=(
                "You are a precise document Q&A assistant. "
                "Answer using ONLY the retrieved context provided. "
                "If the answer is not in the context, say 'I don't know'."
            ),
            context_providers=[search_provider],
        )

    @handler
    async def answer(self, question: str, ctx: WorkflowContext[Never, str]) -> None:
        result = await self._agent.run(question)
        await ctx.yield_output(result)


_rag = RAGExecutor(id="rag")

workflow = WorkflowBuilder(name="RAGWorkflow", start_executor=_rag).build()


async def main():
    result = await workflow.run("What is the refund policy?")
    print(result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())
