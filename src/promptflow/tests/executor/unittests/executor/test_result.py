import pytest

from promptflow.contracts.run_info import RunInfo as NodeRunInfo, Status
from promptflow.executor._result import AggregationResult, BulkResult, LineResult


def get_api_call(type, name, inputs={}, output={}, children=None):
    return {"type": type, "name": f"_._.{name}._", "inputs": inputs, "output": output, "children": children}


@pytest.mark.unittest
class TestBulkResult:
    def get_node_run_infos(self, node_dict, index=None):
        return {
            k: NodeRunInfo(
                node=k,
                flow_run_id="flow_run_id",
                run_id=f"run_id_{k}",
                status=v,
                inputs=[],
                output={},
                metrics={},
                error={},
                parent_run_id="",
                start_time=None,
                end_time=None,
                index=index,
            )
            for k, v in node_dict.items()
        }

    def get_line_results(self, line_dict):
        return [
            LineResult(
                output={},
                aggregation_inputs={},
                run_info=None,
                node_run_infos=self.get_node_run_infos(node_dict=v, index=k),
            )
            for k, v in line_dict.items()
        ]

    def get_bulk_result(self, line_dict, aggr_dict):
        return BulkResult(
            outputs=[],
            metrics={},
            line_results=self.get_line_results(line_dict=line_dict),
            aggr_results=AggregationResult(
                output={},
                metrics={},
                node_run_infos=self.get_node_run_infos(node_dict=aggr_dict)
            )
        )

    def test_get_status_summary(self):
        line_dict = {
            0: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Completed},
            1: {"node_0": Status.Completed, "node_1": Status.Failed, "node_2": Status.Completed},
            2: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Bypassed},
        }
        aggr_dict = {"aggr_0": Status.Completed, "aggr_1": Status.Failed, "aggr_2": Status.Bypassed}
        bulk_result = self.get_bulk_result(line_dict=line_dict, aggr_dict=aggr_dict)

        status_summary = bulk_result.get_status_summary()
        assert status_summary == {
            '__pf__.lines.completed': 2,
            '__pf__.lines.failed': 1,
            "__pf__.nodes.node_0.completed": 3,
            "__pf__.nodes.node_1.completed": 2,
            "__pf__.nodes.node_1.failed": 1,
            "__pf__.nodes.node_2.completed": 2,
            "__pf__.nodes.node_2.bypassed": 1,
            "__pf__.nodes.aggr_0.completed": 1,
            "__pf__.nodes.aggr_1.completed": 0,
            "__pf__.nodes.aggr_2.completed": 0,
        }

    def test_get_openai_metrics(self):
        line_dict = {0: {"node_0": Status.Completed}}
        aggr_dict = {"aggr_0": Status.Completed}
        bulk_result = self.get_bulk_result(line_dict=line_dict, aggr_dict=aggr_dict)

        api_call_1 = get_api_call(
            "LLM", "Completion",
            inputs={"prompt": "Please tell me a joke.", "api_type": "azure", "engine": "text-davinci-003"},
            output={"choices": [{"text": "text"}]}
        )
        api_call_2 = get_api_call(
            "LLM", "Completion",
            inputs={
                "prompt": ["Please tell me a joke.", "Please tell me a joke about fruit."],
                "api_type": "azure", "engine": "text-davinci-003"
            },
            output=[{"choices": [{"text": "text"}]}, {"choices": [{"text": "text"}]}]
        )
        api_call = get_api_call("Chain", "Chain", children=[api_call_1, api_call_2])
        bulk_result.line_results[0].node_run_infos["node_0"].api_calls = [api_call]
        api_call = get_api_call(
            "LLM", "ChatCompletion",
            inputs={
                "messages": [{"system": "You are a helpful assistant.", "user": "Please tell me a joke."}],
                "api_type": "openai", "model": "gpt-35-turbo"
            },
            output={"choices": [{"message": {"content": "content"}}]}
        )
        bulk_result.aggr_results.node_run_infos["aggr_0"].api_calls = [api_call]
        metrics = bulk_result.get_openai_metrics()
        assert metrics == {
            "prompt_tokens": 38,
            "completion_tokens": 4,
            "total_tokens": 42,
        }

    @pytest.mark.parametrize(
        "api_call",
        [
            get_api_call("LLM", "Completion", inputs="invalid"),
            get_api_call("LLM", "Completion", output="invalid"),
            get_api_call("LLM", "Invalid"),
            get_api_call("LLM", "Completion"),
            get_api_call("LLM", "Completion", inputs={"api_type": "azure"}),
            get_api_call("LLM", "ChatCompletion", inputs={"api_type": "azure", "engine": "invalid"})
        ]
    )
    def test_invalid_api_calls(self, api_call):
        line_dict = {0: {"node_0": Status.Completed}}
        bulk_result = self.get_bulk_result(line_dict=line_dict, aggr_dict={})
        bulk_result.line_results[0].node_run_infos["node_0"].api_calls = [api_call]
        metrics = bulk_result.get_openai_metrics()
        assert metrics == {}
