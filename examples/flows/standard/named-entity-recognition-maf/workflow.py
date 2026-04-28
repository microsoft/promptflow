import asyncio
import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

_NER_SYSTEM_PROMPT = (
    "Your task is to find entities of certain type from the given text content.\n"
    "If there're multiple entities, please return them all with comma separated, "
    'e.g. "entity1, entity2, entity3".\n'
    "You should only return the entity list, nothing else.\n"
    'If there\'s no such entity, please return "None".'
)

_NER_USER_TEMPLATE = "Entity type: {entity_type}\nText content: {text}\nEntities:"


@dataclass
class NERInput:
    text: str
    entity_type: str = "job title"


class NERExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="NERAgent",
            instructions=_NER_SYSTEM_PROMPT,
        )

    @handler
    async def extract(self, ner_input: NERInput, ctx: WorkflowContext[str]) -> None:
        user_msg = _NER_USER_TEMPLATE.format(
            entity_type=ner_input.entity_type, text=ner_input.text
        )
        response = await self._agent.run(user_msg)
        await ctx.send_message(response.text)


class CleansingExecutor(Executor):
    @handler
    async def cleanse(self, entities_str: str, ctx: WorkflowContext[Never, List[str]]) -> None:
        parts = entities_str.split(",")
        cleaned = [p.strip(' \t."') for p in parts]
        entities = [p for p in cleaned if len(p) > 0]
        await ctx.yield_output(entities)


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _ner = NERExecutor(id="NER_LLM")
    _cleansing = CleansingExecutor(id="cleansing")
    return (
        WorkflowBuilder(name="NERWorkflow", start_executor=_ner)
        .add_edge(_ner, _cleansing)
        .build()
    )


async def main():
    workflow = create_workflow()
    result = await workflow.run(
        NERInput(
            text="Maxime is a data scientist at Auto Dataset and he lives in Paris, France.",
            entity_type="job title",
        )
    )
    print(result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())
