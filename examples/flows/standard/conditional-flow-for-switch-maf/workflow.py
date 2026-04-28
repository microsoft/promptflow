import asyncio
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

_CLASSIFY_SYSTEM_PROMPT = """\
There is a search bar in the mall APP and users can enter any query in the search bar.

The user may want to search for orders, view product information, or seek recommended products.

Therefore, please classify user intentions into the following three types \
according to the query: product_recommendation, order_search, product_info

Please note that only the above three situations can be returned, and try not to include other return values."""


@dataclass
class ClassifiedQuery:
    query: str
    intention: str


class ClassifyExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ClassifyAgent",
            instructions=_CLASSIFY_SYSTEM_PROMPT,
        )

    @handler
    async def classify(self, query: str, ctx: WorkflowContext[ClassifiedQuery]) -> None:
        response = await self._agent.run(f"The user's query is {query}")
        llm_result = response.text
        intentions_list = ["order_search", "product_info", "product_recommendation"]
        matches = [i for i in intentions_list if i in llm_result.lower()]
        intention = matches[0] if matches else "unknown"
        await ctx.send_message(ClassifiedQuery(query=query, intention=intention))


class OrderSearchExecutor(Executor):
    @handler
    async def search(self, msg: ClassifiedQuery, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output("Your order is being mailed, please wait patiently.")


class ProductInfoExecutor(Executor):
    @handler
    async def info(self, msg: ClassifiedQuery, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output("This product is produced by Microsoft.")


class ProductRecommendationExecutor(Executor):
    @handler
    async def recommend(self, msg: ClassifiedQuery, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(
            "I recommend promptflow to you, which can solve your problem very well."
        )


class DefaultExecutor(Executor):
    @handler
    async def default(self, msg: ClassifiedQuery, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output("Sorry, no results matching your search were found.")


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _classify = ClassifyExecutor(id="classify")
    _order = OrderSearchExecutor(id="order_search")
    _product = ProductInfoExecutor(id="product_info")
    _recommend = ProductRecommendationExecutor(id="product_recommendation")
    _default = DefaultExecutor(id="default")
    return (
        WorkflowBuilder(name="ConditionalSwitchWorkflow", start_executor=_classify)
        .add_edge(_classify, _order, condition=lambda m: m.intention == "order_search")
        .add_edge(_classify, _product, condition=lambda m: m.intention == "product_info")
        .add_edge(_classify, _recommend, condition=lambda m: m.intention == "product_recommendation")
        .add_edge(_classify, _default, condition=lambda m: m.intention == "unknown")
        .build()
    )


async def main():
    workflow = create_workflow()
    result = await workflow.run("When will my order be shipped?")
    print(f"Response: {result.get_outputs()[0]}")


if __name__ == "__main__":
    asyncio.run(main())
