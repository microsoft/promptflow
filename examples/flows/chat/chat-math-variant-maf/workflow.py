import asyncio
import json
import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

# ---------------------------------------------------------------------------
# Variant system prompts (converted from .jinja2 templates)
# ---------------------------------------------------------------------------

VARIANT_0_INSTRUCTIONS = (
    "You are an assistant to calculate the answer to the provided math problems.\n"
    "Please return the final numerical answer only, without any accompanying reasoning or explanation."
)

VARIANT_1_INSTRUCTIONS = """\
You are an assistant to calculate the answer to the provided math problems.
Please think step by step.
Return the final numerical answer only and any accompanying reasoning or explanation seperately as json format.

Here are some examples:

User: A jar contains two red marbles, three green marbles, ten white marbles \
and no other marbles. Two marbles are randomly drawn from this jar without \
replacement. What is the probability that these two marbles drawn will both \
be red? Express your answer as a common fraction.
Assistant: {"Chain of thought": "The total number of marbles is 2+3+10=15. \
The probability that the first marble drawn will be red is 2/15. Then, there \
will be one red left, out of 14. Therefore, the probability of drawing out \
two red marbles will be: (2/15)*(1/14) = 1/105.", "answer": "1/105"}

User: Find the greatest common divisor of 7! and (5!)^2.
Assistant: {"Chain of thought": "7! = 5040 = 2^4 * 3^2 * 5 * 7. \
(5!)^2 = 14400 = 2^6 * 3^2 * 5^2. gcd = 2^4 * 3^2 * 5 = 720.", \
"answer": "720"}"""

VARIANT_2_INSTRUCTIONS = """\
You are an assistant to calculate the answer to the provided math problems.
Please think step by step.
Return the final numerical answer only and any accompanying reasoning or explanation seperately as json format.

Here are some examples:

User: A jar contains two red marbles, three green marbles, ten white marbles \
and no other marbles. Two marbles are randomly drawn from this jar without \
replacement. What is the probability that these two marbles drawn will both \
be red? Express your answer as a common fraction.
Assistant: {"Chain of thought": "The total number of marbles is 2+3+10=15. \
The probability that the first marble drawn will be red is 2/15. Then, there \
will be one red left, out of 14. Therefore, the probability of drawing out \
two red marbles will be: (2/15)*(1/14) = 1/105.", "answer": "1/105"}

User: Find the greatest common divisor of 7! and (5!)^2.
Assistant: {"Chain of thought": "7! = 5040 = 2^4 * 3^2 * 5 * 7. \
(5!)^2 = 14400 = 2^6 * 3^2 * 5^2. gcd = 2^4 * 3^2 * 5 = 720.", \
"answer": "720"}

User: A club has 10 members, 5 boys and 5 girls. Two of the members \
are chosen at random. What is the probability that they are both girls?
Assistant: {"Chain of thought": "There are C(10,2) = 45 ways to choose \
two members, and C(5,2) = 10 ways to choose two girls. Therefore, \
the probability is 10/45 = 2/9.", "answer": "2/9"}

User: Allison, Brian and Noah each have a 6-sided cube. All of the faces \
on Allison's cube have a 5. The faces on Brian's cube are numbered \
1, 2, 3, 4, 5 and 6. Three of the faces on Noah's cube have a 2 and \
three of the faces have a 6. All three cubes are rolled. What is the \
probability that Allison's roll is greater than each of Brian's and Noah's?
Assistant: {"Chain of thought": "Allison always rolls 5. Brian rolls 4 \
or lower with probability 4/6 = 2/3. Noah rolls 2 (less than 5) with \
probability 3/6 = 1/2. So the probability is 2/3 * 1/2 = 1/3.", \
"answer": "1/3"}

User: Compute C(50,2).
Assistant: {"Chain of thought": "C(50,2) = 50!/(2!48!) = (50*49)/(2*1) \
= 1225.", "answer": "1225"}

User: The set S = {1, 2, 3, ..., 49, 50} contains the first 50 positive \
integers. After the multiples of 2 and the multiples of 3 are removed, \
how many integers remain in the set S?
Assistant: {"Chain of thought": "25 even numbers removed, leaving 25 odd \
numbers. Remove odd multiples of 3: 3,9,15,21,27,33,39,45 = 8 numbers. \
25 - 8 = 17.", "answer": "17"}"""

VARIANT_INSTRUCTIONS = {
    "variant_0": VARIANT_0_INSTRUCTIONS,
    "variant_1": VARIANT_1_INSTRUCTIONS,
    "variant_2": VARIANT_2_INSTRUCTIONS,
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ChatInput:
    question: str
    chat_history: list = field(default_factory=list)
    variant: str = "variant_0"


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


class InputExecutor(Executor):
    """Formats the chat history and question into a single prompt string."""

    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[str]) -> None:
        parts: list[str] = []
        if chat_input.chat_history:
            for turn in chat_input.chat_history:
                parts.append(f"User: {turn['inputs']['question']}")
                parts.append(f"Assistant: {turn['outputs']['answer']}")
        parts.append(chat_input.question)
        await ctx.send_message("\n".join(parts))


class ChatExecutor(Executor):
    """Calls the LLM with the selected variant instructions."""

    def __init__(self, variant: str = "variant_0", **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ChatMathAgent",
            instructions=VARIANT_INSTRUCTIONS[variant],
        )

    @handler
    async def call_llm(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        response = await self._agent.run(prompt)
        await ctx.send_message(response.text)


class ExtractResultExecutor(Executor):
    """Extracts the final answer from the LLM response (mirrors extract_result.py)."""

    @handler
    async def extract(self, llm_output: str, ctx: WorkflowContext[Never, str]) -> None:
        cleaned = re.sub(r'[$\\!]', '', llm_output)
        try:
            json_answer = json.loads(cleaned)
            answer = json_answer["answer"]
        except Exception:
            answer = cleaned
        await ctx.yield_output(answer)


# ---------------------------------------------------------------------------
# Workflow builder
# ---------------------------------------------------------------------------


def build_workflow(variant: str = "variant_0"):
    """Build the chat-math workflow for the given variant."""
    _input = InputExecutor(id="input")
    _chat = ChatExecutor(id="chat", variant=variant)
    _extract = ExtractResultExecutor(id="extract_result")

    return (
        WorkflowBuilder(name="ChatMathVariantWorkflow", start_executor=_input)
        .add_edge(_input, _chat)
        .add_edge(_chat, _extract)
        .build()
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    variant = os.environ.get("CHAT_VARIANT", "variant_0")
    workflow = build_workflow(variant)

    result = await workflow.run(
        ChatInput(question="1+1=?", variant=variant)
    )
    print("Answer:", result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())
