import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

# ---------------------------------------------------------------------------
# Prompt templates (from .jinja2 files)
# ---------------------------------------------------------------------------

MODIFY_QUERY_INSTRUCTIONS = """\
Given the following conversation history and the users next question, \
rephrase the question to be a stand alone question.
If the conversation is irrelevant or empty, just restate the original question.
Do not add more details than necessary to the question."""

CHECK_RELEVANCE_INSTRUCTIONS = """\
You are a helpful assistant that knows well about a product named promptflow. Here is instruction of the product:

[Instruction]
Prompt flow is a suite of development tools designed to streamline the end-to-end development cycle of LLM-based AI applications, from ideation, prototyping, testing, evaluation to production deployment and monitoring. It makes prompt engineering much easier and enables you to build LLM apps with production quality.

With prompt flow, you will be able to:
Create and iteratively develop flow, debug and iterate your flows, evaluate flow quality and performance, and deploy your flow to the serving platform you choose.

The key concepts in promptflow includes:
flow, connection, tool, variant, variants, node, nodes, input, inputs, output, outputs, prompt, run, evaluation flow, conditional flow, activate config, deploy flow and develop flow in azure cloud.
Also include open source, stream, streaming, function calling, response format, model, tracing, vision, bulk test, docstring, docker image, json, jsonl and python package.
[End Instruction]

Your job is to determine whether user's question is related to the product or the key concepts or information about yourself.
You do not need to give the answer to the question. Simply return a number between 0 and 10 to represent the correlation between the question and the product.
Return 0 if it is totally not related. Return 10 if it is highly related.
Do not return anything else except the number."""

ANSWER_WITH_CONTEXT_INSTRUCTIONS = """\
You are an AI assistant that designed to extract answer for user's questions from given context and conversation history.
Politely refuse to answer the question if the answer cannot be formed strictly using the provided context and conversation history.
Your answer should be as precise as possible, and should only come from the context. \
Add citation after each sentence when possible in a form "{Your answer}. [Reference](citation)"."""

REFUSE_MESSAGE = (
    "Unfortunately, I'm unable to address this question since it appears to be "
    "unrelated to prompt flow. Could you please either propose a different question "
    "or rephrase your inquiry to align more closely with prompt flow?"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ChatInput:
    question: str
    chat_history: list = field(default_factory=list)


@dataclass
class StandaloneQuery:
    """Output of the query rewriting step."""
    question: str
    chat_history: list


@dataclass
class RelevanceResult:
    """Carries the standalone query plus the relevance flag."""
    question: str
    chat_history: list
    not_relevant: bool


@dataclass
class PromptReady:
    """Carries the final prompt text to send to the answering LLM."""
    prompt_text: str


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


class InputExecutor(Executor):
    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[ChatInput]) -> None:
        await ctx.send_message(chat_input)


class ModifyQueryExecutor(Executor):
    """LLM: rewrites the question as a standalone question using chat history."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT4", "gpt-4"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ModifyQueryAgent",
            instructions=MODIFY_QUERY_INSTRUCTIONS,
        )

    @handler
    async def rewrite(self, chat_input: ChatInput, ctx: WorkflowContext[StandaloneQuery]) -> None:
        parts: list[str] = ["conversation:\n\nchat history:"]
        for turn in chat_input.chat_history:
            parts.append(f"user: {turn['inputs']['question']}")
            parts.append(f"assistant: {turn['outputs'].get('output', '')}")
        parts.append(f"\nFollow up Input: {chat_input.question}")
        parts.append("Standalone Question:")

        response = await self._agent.run("\n".join(parts))
        await ctx.send_message(
            StandaloneQuery(
                question=response.text.strip(),
                chat_history=chat_input.chat_history,
            )
        )


class CheckRelevanceExecutor(Executor):
    """LLM + Python: scores query relevance (0-10) and decides if it's off-topic."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT35", "gpt-35-turbo"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="CheckRelevanceAgent",
            instructions=CHECK_RELEVANCE_INSTRUCTIONS,
        )

    @handler
    async def check(self, sq: StandaloneQuery, ctx: WorkflowContext[RelevanceResult]) -> None:
        response = await self._agent.run(sq.question)
        score = response.text.strip()
        not_relevant = score == "0"
        await ctx.send_message(
            RelevanceResult(
                question=sq.question,
                chat_history=sq.chat_history,
                not_relevant=not_relevant,
            )
        )


class LookupAndAnswerExecutor(Executor):
    """Conditional: if relevant, looks up docs and builds answer prompt; if not, refuses.

    NOTE: The original flow uses `promptflow_vectordb` for index lookup.
    Replace `_search_index()` with your own search implementation
    (e.g. Azure AI Search, FAISS, etc.).
    """

    @handler
    async def build_prompt(self, rr: RelevanceResult, ctx: WorkflowContext[PromptReady]) -> None:
        if rr.not_relevant:
            await ctx.send_message(PromptReady(prompt_text=REFUSE_MESSAGE))
            return

        # --- Index lookup placeholder ---
        # Replace this with a real vector / keyword search.
        contexts = _search_index(rr.question)

        # Build the answer prompt (mirrors answer_question_prompt.jinja2)
        parts: list[str] = [
            "You are an AI assistant that designed to extract answer for user's questions "
            "from given context and conversation history.",
            "Politely refuse to answer the question if the answer cannot be formed "
            "strictly using the provided context and conversation history.",
            'Your answer should be as precise as possible, and should only come from the context. '
            'Add citation after each sentence when possible in a form "{Your answer}. [Reference](citation)".',
            "",
            contexts,
            "",
            "chat history:",
        ]
        for turn in rr.chat_history:
            parts.append(f"user: {turn['inputs']['question']}")
            parts.append(f"assistant: {turn['outputs'].get('output', '')}")
        parts.append(f"\nuser:\n{rr.question}")

        await ctx.send_message(PromptReady(prompt_text="\n".join(parts)))


class AnswerExecutor(Executor):
    """LLM: generates the final answer from the selected prompt."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT4", "gpt-4"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="AnswerAgent",
            instructions=ANSWER_WITH_CONTEXT_INSTRUCTIONS,
        )

    @handler
    async def answer(self, pr: PromptReady, ctx: WorkflowContext[Never, str]) -> None:
        # If it's the refusal message, pass it through directly
        if pr.prompt_text == REFUSE_MESSAGE:
            await ctx.yield_output(REFUSE_MESSAGE)
            return

        response = await self._agent.run(pr.prompt_text)
        await ctx.yield_output(response.text)


# ---------------------------------------------------------------------------
# Index search placeholder
# ---------------------------------------------------------------------------


def _search_index(question: str) -> str:
    """Placeholder for vector/keyword index lookup.

    Replace this with your actual search implementation, e.g.:
        - Azure AI Search
        - FAISS local index
        - promptflow_vectordb common_index_lookup

    Returns a formatted context string.
    """
    return (
        "Content: [No index configured — replace _search_index() in workflow.py "
        "with your search implementation.]\nSource: N/A"
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

_input = InputExecutor(id="input")
_modify_query = ModifyQueryExecutor(id="modify_query")
_check_relevance = CheckRelevanceExecutor(id="check_relevance")
_lookup_and_answer = LookupAndAnswerExecutor(id="lookup_and_answer")
_answer = AnswerExecutor(id="answer")

workflow = (
    WorkflowBuilder(name="PromptflowCopilotWorkflow", start_executor=_input)
    .add_edge(_input, _modify_query)
    .add_edge(_modify_query, _check_relevance)
    .add_edge(_check_relevance, _lookup_and_answer)
    .add_edge(_lookup_and_answer, _answer)
    .build()
)


async def main():
    # Relevant question
    result = await workflow.run(ChatInput(question="How do I deploy a flow?"))
    print("Answer:", result.get_outputs()[0])

    # Irrelevant question
    result = await workflow.run(ChatInput(question="What is the weather today?"))
    print("Answer:", result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())
