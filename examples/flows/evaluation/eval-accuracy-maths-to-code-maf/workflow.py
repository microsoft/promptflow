import asyncio
from dataclasses import dataclass
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


@dataclass
class EvalInput:
    groundtruth: str
    prediction: str


class LineProcessExecutor(Executor):
    @handler
    async def process(self, input: EvalInput, ctx: WorkflowContext[Never, int]) -> None:
        processed_result = 0

        if input.prediction == "JSONDecodeError" or input.prediction.startswith("Unknown Error:"):
            await ctx.yield_output(-1)
            return

        try:
            groundtruth = float(input.groundtruth)
            prediction = float(input.prediction)
        except ValueError:
            await ctx.yield_output(-1)
            return

        if round(prediction, 2) == round(groundtruth, 2):
            processed_result = 1

        await ctx.yield_output(processed_result)


def create_workflow():
    _line_process = LineProcessExecutor(id="line_process")
    return WorkflowBuilder(name="EvalAccuracyMathsRow", start_executor=_line_process).build()
