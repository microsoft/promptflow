from dataclasses import dataclass
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


def string_to_number(raw_string: str) -> float:
    float_number = 0.0
    try:
        float_number = float(raw_string)
    except Exception:
        if '/' in raw_string:
            split_list = raw_string.split('/')
            if len(split_list) == 2:
                numerator, denominator = split_list
                try:
                    float_number = float(numerator) / float(denominator)
                except Exception:
                    return None
            else:
                return None
        else:
            return None
    return float_number


@dataclass
class EvalInput:
    groundtruth: str
    prediction: str


class LineProcessExecutor(Executor):
    @handler
    async def process(self, input: EvalInput, ctx: WorkflowContext[Never, int]) -> None:
        pred_float = string_to_number(input.prediction)
        if pred_float is None:
            await ctx.yield_output(-1)
            return
        gt_float = string_to_number(input.groundtruth)
        if gt_float is None:
            await ctx.yield_output(-1)
            return
        if round(pred_float, 10) == round(gt_float, 10):
            await ctx.yield_output(1)
        else:
            await ctx.yield_output(-1)


def create_workflow():
    _line_process = LineProcessExecutor(id="line_process")
    return WorkflowBuilder(name="EvalChatMathRow", start_executor=_line_process).build()
