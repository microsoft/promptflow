import asyncio
import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from wiki_search import search
from python_repl import python

load_dotenv()

_TRIGGERING_PROMPT = (
    "Determine which next function to use, and respond using stringfield JSON object.\n"
    "If you have completed all your tasks, make sure to use the 'finish' function to signal "
    "and remember show your results."
)


def _search_tool(entity: str, count: int = 10) -> str:
    """Search Wikipedia for an entity and return the first sentences."""
    return search(entity, count)


def _python_tool(command: str) -> str:
    """Execute a Python command and return the output."""
    return python(command)


def _finish_tool(response: str) -> str:
    """Signal that all goals are completed and show results."""
    return response


@dataclass
class AutoGPTInput:
    name: str = "FilmTriviaGPT"
    goals: List[str] = field(default_factory=lambda: [
        "Introduce 'Lord of the Rings' film trilogy including the film title, "
        "release year, director, current age of the director, production company "
        "and a brief summary of the film."
    ])
    role: str = (
        "an AI specialized in film trivia that provides accurate and up-to-date "
        "information about movies, directors, actors, and more."
    )


class AutoGPTExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="AutoGPTAgent",
            instructions="",  # will be set dynamically per run
            tools=[_search_tool, _python_tool, _finish_tool],
        )

    @handler
    async def process(self, gpt_input: AutoGPTInput, ctx: WorkflowContext[Never, str]) -> None:
        # Build system prompt
        system_prompt = (
            f"You are {gpt_input.name}, {gpt_input.role}\n"
            "Play to your strengths as an LLM and pursue simple strategies "
            "with no legal complications to complete all goals.\n"
            "Your decisions must always be made independently without seeking "
            "user assistance.\n\n"
            "Performance Evaluation:\n"
            "1. Continuously review and analyze your actions to ensure you are "
            "performing to the best of your abilities.\n"
            "2. Constructively self-criticize your big-picture behavior constantly.\n"
            "3. Reflect on past decisions and strategies to refine your approach.\n"
            "4. Every command has a cost, so be smart and efficient. "
            "Aim to complete tasks in the least number of steps.\n"
        )

        goals_text = "\n".join(f"{i + 1}. {g}" for i, g in enumerate(gpt_input.goals))
        user_prompt = f"Goals:\n\n{goals_text}\n\n{_TRIGGERING_PROMPT}"

        self._agent._instructions = system_prompt

        response = await self._agent.run(user_prompt)
        await ctx.yield_output(response.text)


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _executor = AutoGPTExecutor(id="autogpt")
    return (
        WorkflowBuilder(name="AutonomousAgentWorkflow", start_executor=_executor)
        .build()
    )


async def main():
    workflow = create_workflow()
    result = await workflow.run(
        AutoGPTInput(
            name="FilmTriviaGPT",
            goals=[
                "Introduce 'Lord of the Rings' film trilogy including the film title, "
                "release year, director, current age of the director, production company "
                "and a brief summary of the film."
            ],
            role=(
                "an AI specialized in film trivia that provides accurate and up-to-date "
                "information about movies, directors, actors, and more."
            ),
        )
    )
    print(f"Output:\n{result.get_outputs()[0]}")


if __name__ == "__main__":
    asyncio.run(main())
