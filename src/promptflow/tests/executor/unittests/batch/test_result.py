from datetime import datetime

import pytest

from promptflow.batch._result import BatchResult, LineError
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.executor._result import AggregationResult, LineResult


def get_api_call(type, name, inputs={}, output={}, children=None):
    return {"type": type, "name": name, "inputs": inputs, "output": output, "children": children}


@pytest.mark.unittest
class TestBatchResult:
    def get_node_run_infos(self, node_dict, index=None, api_calls=None):
        return {
            k: NodeRunInfo(
                node=k,
                flow_run_id="flow_run_id",
                run_id=f"run_id_{k}",
                status=v,
                inputs=[],
                output={},
                metrics={},
                error={"code": "UserError", "message": "test message"} if v == Status.Failed else None,
                parent_run_id="",
                start_time=None,
                end_time=None,
                index=index,
                api_calls=api_calls,
            )
            for k, v in node_dict.items()
        }

    def get_flow_run_info(self, status_dict: dict, index: int):
        status = Status.Failed if any(status == Status.Failed for status in status_dict.values()) else Status.Completed
        error = {"code": "UserError", "message": "test message"} if status == Status.Failed else None
        return FlowRunInfo(
            run_id="run_id",
            status=status,
            error=error,
            inputs={},
            output={},
            metrics={},
            request=None,
            parent_run_id="",
            root_run_id="",
            source_run_id="",
            flow_id="",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            index=index,
        )

    def get_line_results(self, line_dict, api_calls=None):
        return [
            LineResult(
                output={},
                aggregation_inputs={},
                run_info=self.get_flow_run_info(status_dict=v, index=k),
                node_run_infos=self.get_node_run_infos(node_dict=v, index=k, api_calls=api_calls),
            )
            for k, v in line_dict.items()
        ]

    def get_batch_result(self, line_dict, aggr_dict, line_api_calls=None, aggr_api_calls=None):
        line_results = self.get_line_results(line_dict=line_dict, api_calls=line_api_calls)
        aggr_result = AggregationResult(
            output={}, metrics={}, node_run_infos=self.get_node_run_infos(node_dict=aggr_dict, api_calls=aggr_api_calls)
        )
        return BatchResult.create(
            datetime.utcnow(), datetime.utcnow(), line_results=line_results, aggr_result=aggr_result
        )

    def test_node_status(self):
        line_dict = {
            0: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Completed},
            1: {"node_0": Status.Completed, "node_1": Status.Failed, "node_2": Status.Completed},
            2: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Bypassed},
        }
        aggr_dict = {"aggr_0": Status.Completed, "aggr_1": Status.Failed, "aggr_2": Status.Bypassed}
        batch_result = self.get_batch_result(line_dict=line_dict, aggr_dict=aggr_dict)

        assert batch_result.total_lines == 3
        assert batch_result.completed_lines == 2
        assert batch_result.failed_lines == 1
        assert batch_result.node_status == {
            "node_0.completed": 3,
            "node_1.completed": 2,
            "node_1.failed": 1,
            "node_2.completed": 2,
            "node_2.bypassed": 1,
            "aggr_0.completed": 1,
            "aggr_1.failed": 1,
            "aggr_2.bypassed": 1,
        }

    def test_system_metrics(self):
        from openai.types.completion import Completion, CompletionChoice

        line_dict = {0: {"node_0": Status.Completed}}
        aggr_dict = {"aggr_0": Status.Completed}

        api_call_1 = get_api_call(
            "LLM",
            "openai.resources.completions.Completions.create",
            inputs={"prompt": "Please tell me a joke.", "model": "text-davinci-003"},
            output={"choices": [{"text": "text"}]},
        )
        api_call_2 = get_api_call(
            "LLM",
            "openai.resources.completions.Completions.create",
            inputs={
                "prompt": ["Please tell me a joke.", "Please tell me a joke about fruit."],
                "model": "text-davinci-003",
            },
            output=[
                Completion(
                    choices=[CompletionChoice(text="text", finish_reason="stop", index=0, logprobs=None)],
                    id="id",
                    created=0,
                    model="model",
                    object="text_completion",
                ),
                Completion(
                    choices=[CompletionChoice(text="text", finish_reason="stop", index=0, logprobs=None)],
                    id="id",
                    created=0,
                    model="model",
                    object="text_completion",
                ),
            ],
        )
        line_api_calls = get_api_call("Chain", "Chain", children=[api_call_1, api_call_2])
        aggr_api_call = get_api_call(
            "LLM",
            "openai.resources.chat.completions.Completions.create",
            inputs={
                "messages": [{"system": "You are a helpful assistant.", "user": "Please tell me a joke."}],
                "model": "gpt-35-turbo",
            },
            output={"choices": [{"message": {"content": "content"}}]},
        )
        batch_result = self.get_batch_result(
            line_dict=line_dict, aggr_dict=aggr_dict, line_api_calls=[line_api_calls], aggr_api_calls=[aggr_api_call]
        )
        assert batch_result.system_metrics.total_tokens == 42
        assert batch_result.system_metrics.prompt_tokens == 38
        assert batch_result.system_metrics.completion_tokens == 4
        assert int(batch_result.system_metrics.duration) == 0

    @pytest.mark.parametrize(
        "api_call",
        [
            get_api_call("LLM", "Completion", inputs="invalid"),
            get_api_call("LLM", "Completion", output="invalid"),
            get_api_call("LLM", "Invalid"),
            get_api_call("LLM", "Completion"),
            get_api_call("LLM", "Completion", inputs={"api_type": "azure"}),
            get_api_call("LLM", "ChatCompletion", inputs={"api_type": "azure", "engine": "invalid"}),
        ],
    )
    def test_invalid_api_calls(self, api_call):
        line_dict = {0: {"node_0": Status.Completed}}
        batch_result = self.get_batch_result(line_dict=line_dict, aggr_dict={}, line_api_calls=[api_call])
        assert batch_result.system_metrics.total_tokens == 0
        assert batch_result.system_metrics.completion_tokens == 0
        assert batch_result.system_metrics.prompt_tokens == 0

    def test_error_summary(self):
        line_dict = {
            0: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Completed},
            1: {"node_0": Status.Completed, "node_1": Status.Failed, "node_2": Status.Completed},
            2: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Bypassed},
        }
        aggr_dict = {
            "aggr_0": Status.Completed,
            "aggr_1": Status.Failed,
            "aggr_2": Status.Bypassed,
            "aggr_4": Status.Failed,
        }
        batch_result = self.get_batch_result(line_dict=line_dict, aggr_dict=aggr_dict)
        assert batch_result.total_lines == 3
        assert batch_result.failed_lines == 1
        assert batch_result.error_summary.failed_system_error_lines == 0
        assert batch_result.error_summary.failed_user_error_lines == 1
        assert batch_result.error_summary.error_list == [
            LineError(line_number=1, error={"code": "UserError", "message": "test message"}),
        ]
        assert batch_result.error_summary.aggr_error_dict == {
            "aggr_1": {"code": "UserError", "message": "test message"},
            "aggr_4": {"code": "UserError", "message": "test message"},
        }
