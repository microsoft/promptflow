from dataclasses import dataclass
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


@dataclass
class EvalInput:
    groundtruth: str
    prediction: str


class GradeExecutor(Executor):
    @handler
    async def grade(self, input: EvalInput, ctx: WorkflowContext[Never, str]) -> None:
        result = "Correct" if input.groundtruth.lower() == input.prediction.lower() else "Incorrect"
        await ctx.yield_output(result)


def create_workflow():
    _grade = GradeExecutor(id="grade")
    return WorkflowBuilder(name="EvalClassificationAccuracyRow", start_executor=_grade).build()
