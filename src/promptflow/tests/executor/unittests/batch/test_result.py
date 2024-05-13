from datetime import datetime

import pytest

from promptflow.batch._result import BatchResult, ErrorSummary, LineError, SystemMetrics
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.executor._result import AggregationResult, LineResult


def get_node_run_infos(node_dict: dict, index=None, api_calls=None, system_metrics=None):
    return {
        k: NodeRunInfo(
            node=k,
            flow_run_id="flow_run_id",
            run_id=f"{index}_run_id_{k}",
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
            system_metrics=system_metrics,
        )
        for k, v in node_dict.items()
    }


def get_flow_run_info(status_dict: dict, index: int, api_calls=None, system_metrics=None):
    status = Status.Failed if any(status == Status.Failed for status in status_dict.values()) else Status.Completed
    error = {"code": "UserError", "message": "test message"} if status == Status.Failed else None
    children = []
    aggregated_tokens = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    for i in range(len(status_dict)):
        if api_calls is not None:
            children.extend(api_calls)
        if system_metrics is not None:
            for k, _ in aggregated_tokens.items():
                if k in system_metrics:
                    aggregated_tokens[k] += system_metrics[k]
    return FlowRunInfo(
        run_id=f"{index}_run_id",
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
        api_calls=[get_api_call("Flow", "Flow", children=children)] if api_calls else None,
        system_metrics=aggregated_tokens if system_metrics else None,
    )


def get_line_results(line_dict: dict, api_calls=None, system_metrics=None):
    return [
        LineResult(
            output={},
            aggregation_inputs={},
            run_info=get_flow_run_info(status_dict=v, index=k, api_calls=api_calls, system_metrics=system_metrics),
            node_run_infos=get_node_run_infos(node_dict=v, index=k, api_calls=api_calls, system_metrics=system_metrics),
        )
        for k, v in line_dict.items()
    ]


def get_aggregation_result(aggr_dict: dict, api_calls=None, system_metrics=None):
    return AggregationResult(
        output={},
        metrics={},
        node_run_infos=get_node_run_infos(node_dict=aggr_dict, api_calls=api_calls, system_metrics=system_metrics),
    )


def get_batch_result(line_dict, aggr_dict, line_api_calls=None, aggr_api_calls=None):
    line_results = get_line_results(line_dict=line_dict, api_calls=line_api_calls)
    aggr_result = get_aggregation_result(aggr_dict=aggr_dict, api_calls=aggr_api_calls)
    return BatchResult.create(datetime.utcnow(), datetime.utcnow(), line_results=line_results, aggr_result=aggr_result)


def get_api_call(type, name, inputs={}, output={}, children=None):
    return {"type": type, "name": name, "inputs": inputs, "output": output, "children": children}


@pytest.mark.unittest
class TestBatchResult:
    def test_node_status(self):
        line_dict = {
            0: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Completed},
            1: {"node_0": Status.Completed, "node_1": Status.Failed, "node_2": Status.Completed},
            2: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Bypassed},
        }
        aggr_dict = {"aggr_0": Status.Completed, "aggr_1": Status.Failed, "aggr_2": Status.Bypassed}
        batch_result = get_batch_result(line_dict=line_dict, aggr_dict=aggr_dict)

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
            "openai_completion",
            inputs={"prompt": "Please tell me a joke.", "model": "text-davinci-003"},
            output={"choices": [{"text": "text"}]},
        )
        api_call_2 = get_api_call(
            "LLM",
            "openai_completion",
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
            "openai_chat",
            inputs={
                "messages": [{"system": "You are a helpful assistant.", "user": "Please tell me a joke."}],
                "model": "gpt-35-turbo",
            },
            output={"choices": [{"message": {"content": "content"}}]},
        )
        batch_result = get_batch_result(
            line_dict=line_dict, aggr_dict=aggr_dict, line_api_calls=[line_api_calls], aggr_api_calls=[aggr_api_call]
        )
        assert batch_result.system_metrics.total_tokens == 42
        assert batch_result.system_metrics.prompt_tokens == 38
        assert batch_result.system_metrics.completion_tokens == 4
        system_metrics_dict = {
            "total_tokens": 42,
            "prompt_tokens": 38,
            "completion_tokens": 4,
        }
        assert system_metrics_dict.items() <= batch_result.system_metrics.to_dict().items()

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
        batch_result = get_batch_result(line_dict=line_dict, aggr_dict={}, line_api_calls=[api_call])
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
        batch_result = get_batch_result(line_dict=line_dict, aggr_dict=aggr_dict)
        assert batch_result.total_lines == 3
        assert batch_result.failed_lines == 1
        assert batch_result.error_summary.failed_system_error_lines == 0
        assert batch_result.error_summary.failed_user_error_lines == 1
        assert batch_result.error_summary.error_list == [
            LineError(line_number=1, error={"code": "UserError", "message": "test message"}),
        ]
        assert batch_result.error_summary.error_list[0].to_dict() == {
            "line_number": 1,
            "error": {
                "code": "UserError",
                "message": "test message",
            },
        }
        assert batch_result.error_summary.aggr_error_dict == {
            "aggr_1": {"code": "UserError", "message": "test message"},
            "aggr_4": {"code": "UserError", "message": "test message"},
        }


@pytest.mark.unittest
class TestErrorSummary:
    def test_create(self):
        line_dict = {
            0: {"node_0": Status.Failed, "node_1": Status.Completed, "node_2": Status.Completed},
            1: {"node_0": Status.Completed, "node_1": Status.Failed, "node_2": Status.Completed},
        }
        line_results = get_line_results(line_dict)
        line_results[0].run_info.error = {"code": "SystemError", "message": "test system error message"}
        aggr_dict = {"aggr_0": Status.Completed, "aggr_1": Status.Failed}
        aggr_result = get_aggregation_result(aggr_dict)
        error_summary = ErrorSummary.create(line_results, aggr_result)
        assert error_summary.failed_user_error_lines == 1
        assert error_summary.failed_system_error_lines == 1
        assert error_summary.error_list == [
            LineError(line_number=0, error={"code": "SystemError", "message": "test system error message"}),
            LineError(line_number=1, error={"code": "UserError", "message": "test message"}),
        ]
        assert error_summary.aggr_error_dict == {"aggr_1": {"code": "UserError", "message": "test message"}}


@pytest.mark.unittest
class TestSystemMetrics:
    def test_create(slef):
        line_dict = {
            0: {"node_0": Status.Completed, "node_1": Status.Completed},
            1: {"node_0": Status.Completed, "node_1": Status.Completed},
        }
        line_system_metrics = {
            "total_tokens": 5,
            "prompt_tokens": 3,
            "completion_tokens": 2,
        }
        line_results = get_line_results(line_dict, system_metrics=line_system_metrics)
        aggr_dict = {"aggr_0": Status.Completed}
        # invalid system metrics
        aggr_system_metrics = {
            "total_tokens": 10,
            "prompt_tokens": 6,
        }
        aggr_result = get_aggregation_result(aggr_dict, system_metrics=aggr_system_metrics)
        system_metrics = SystemMetrics.create(datetime.utcnow(), datetime.utcnow(), line_results, aggr_result)
        assert system_metrics.total_tokens == 30
        assert system_metrics.prompt_tokens == 18
        assert system_metrics.completion_tokens == 8
        system_metrics_dict = {
            "total_tokens": 30,
            "prompt_tokens": 18,
            "completion_tokens": 8,
        }
        assert system_metrics_dict.items() <= system_metrics.to_dict().items()
