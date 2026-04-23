import asyncio
from dataclasses import dataclass
from typing import List
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


@dataclass
class EvalInput:
    entities: List[str]
    ground_truth: str


def cleansing(entities_str: str) -> List[str]:
    parts = entities_str.split(",")
    cleaned_parts = [part.strip(" \t.\"") for part in parts]
    return [part for part in cleaned_parts if len(part) > 0]


def is_match(answer: List[str], ground_truth: List[str],
             ignore_case: bool, ignore_order: bool, allow_partial: bool) -> bool:
    if ignore_case:
        answer = [a.lower() for a in answer]
        ground_truth = [g.lower() for g in ground_truth]
    if ignore_order:
        answer.sort()
        ground_truth.sort()
    if allow_partial:
        x = [a for a in answer if a in ground_truth]
        return x == answer
    return answer == ground_truth


class EntityMatchExecutor(Executor):
    @handler
    async def process(self, input: EvalInput, ctx: WorkflowContext[Never, dict]) -> None:
        ground_truth_list = cleansing(input.ground_truth)

        exact_match = 0
        partial_match = 0
        if is_match(input.entities, ground_truth_list, ignore_case=True, ignore_order=True, allow_partial=False):
            exact_match = 1
        if is_match(input.entities, ground_truth_list, ignore_case=True, ignore_order=True, allow_partial=True):
            partial_match = 1

        await ctx.yield_output({
            "exact_match": exact_match,
            "partial_match": partial_match,
            "answer": input.entities,
            "ground_truth": ground_truth_list,
        })


def create_workflow():
    _matcher = EntityMatchExecutor(id="entity_match")
    return WorkflowBuilder(name="EvalEntityMatchRow", start_executor=_matcher).build()
