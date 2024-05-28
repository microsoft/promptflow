import pytest

from promptflow._core._errors import RunRecordNotFound
from promptflow._core.run_tracker import RunTracker
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.run_info import Status
from promptflow.tracing.contracts.iterator_proxy import IteratorProxy


class UnserializableClass:
    def __init__(self, data: str):
        self.data = data


@pytest.mark.unittest
class TestRunTracker:
    def test_run_tracker(self):
        # TODO: Refactor this test case, it's very confusing now.
        # Initialize run tracker with dummy run storage
        run_tracker = RunTracker.init_dummy()

        # Start flow run
        run_tracker.start_flow_run("test_flow_id", "test_root_run_id", "test_flow_run_id")
        assert len(run_tracker._flow_runs) == 1
        assert run_tracker._current_run_id == "test_flow_run_id"
        flow_input = {"flow_input": "input_0"}
        run_tracker.set_inputs("test_flow_run_id", flow_input)

        # Start node runs
        run_info = run_tracker.start_node_run("node_0", "test_root_run_id", "test_flow_run_id", "run_id_0", index=0)
        run_info.index = 0
        run_info = run_tracker.start_node_run("node_0", "test_root_run_id", "test_flow_run_id", "run_id_1", index=1)
        run_info.index = 1
        run_tracker.start_node_run("node_aggr", "test_root_run_id", "test_flow_run_id", "run_id_aggr", index=None)
        assert len(run_tracker._node_runs) == 3
        assert run_tracker._current_run_id == "run_id_aggr"

        # Test collect_all_run_infos_as_dicts
        run_tracker.allow_generator_types = True
        run_tracker.set_inputs(
            "run_id_0", {"input": "input_0", "connection": AzureOpenAIConnection("api_key", "api_base")}
        )
        run_tracker.set_inputs("run_id_1", {"input": "input_1", "generator": IteratorProxy(item for item in range(10))})
        run_infos = run_tracker.collect_all_run_infos_as_dicts()
        assert len(run_infos["flow_runs"]) == 1
        assert len(run_infos["node_runs"]) == 3
        assert run_infos["node_runs"][0]["inputs"] == {"input": "input_0", "connection": "AzureOpenAIConnection"}
        assert run_infos["node_runs"][1]["inputs"] == {"input": "input_1", "generator": []}

        # Test end run with normal result
        result = {"result": "result"}
        run_info_0 = run_tracker.end_run(run_id="run_id_0", result=result)
        assert run_info_0.status == Status.Completed
        assert run_info_0.output == result

        # Test end run with unserializable result
        result = {"unserialized_value": UnserializableClass("test")}
        run_info_1 = run_tracker.end_run(run_id="run_id_1", result=result)
        assert run_info_1.status == Status.Completed
        assert run_info_1.output == str(result)

        # Test end run with invalid run id
        with pytest.raises(RunRecordNotFound):
            run_tracker.end_run(run_id="invalid_run_id")

        # Test end run with exception
        ex = Exception("Failed")
        run_info_aggr = run_tracker.end_run(run_id="run_id_aggr", ex=ex)
        assert run_info_aggr.status == Status.Failed
        assert run_info_aggr.error["message"] == "Failed"

        # Test end flow run with unserializable result
        result = {"unserialized_value": UnserializableClass("test")}
        run_info_flow = run_tracker.end_run(run_id="test_flow_run_id", result=result)
        assert run_info_flow.status == Status.Failed
        assert "The output 'unserialized_value' for flow is incorrect." in run_info_flow.error["message"]

        # Test _update_flow_run_info_with_node_runs
        run_info_0.api_calls, run_info_0.system_metrics = [{"name": "caht"}], {"total_tokens": 10}
        run_info_1.api_calls, run_info_1.system_metrics = [{"name": "completion"}], {"total_tokens": 20}
        run_info_aggr.api_calls, run_info_aggr.system_metrics = [{"name": "caht"}, {"name": "completion"}], {
            "total_tokens": 30
        }
        run_tracker._update_flow_run_info_with_node_runs(run_info_flow)

        assert len(run_info_flow.api_calls) == 1, "There should be only one top level api call for flow run."
        assert run_info_flow.system_metrics["total_tokens"] == 60
        assert run_info_flow.api_calls[0]["name"] == "flow"
        assert run_info_flow.api_calls[0]["node_name"] == "flow"
        assert run_info_flow.api_calls[0]["type"] == "Flow"
        assert run_info_flow.api_calls[0]["system_metrics"]["total_tokens"] == 60
        assert run_info_flow.api_calls[0]["inputs"] == flow_input
        assert run_info_flow.api_calls[0]["output"] is None
        assert (
            "The output 'unserialized_value' for flow is incorrect." in run_info_flow.api_calls[0]["error"]["message"]
        )
        assert isinstance(run_info_flow.api_calls[0]["start_time"], float)
        assert isinstance(run_info_flow.api_calls[0]["end_time"], float)
        assert len(run_info_flow.api_calls[0]["children"]) == 4, "There should be 4 children under root."

        # Test get_status_summary
        status_summary = run_tracker.get_status_summary("test_root_run_id")
        assert status_summary == {
            "__pf__.lines.completed": 0,
            "__pf__.lines.failed": 1,
            "__pf__.nodes.node_0.completed": 2,
            "__pf__.nodes.node_aggr.completed": 0,
        }

    def test_run_tracker_flow_run_without_node_run(self):
        """When line timeout, there will be flow run info without node run info."""
        # Initialize run tracker with dummy run storage
        run_tracker = RunTracker.init_dummy()

        # Start flow run
        run_tracker.start_flow_run("test_flow_id", "test_root_run_id", "test_flow_run_id_0", index=0)
        run_tracker.end_run("test_flow_run_id_0", ex=Exception("Timeout"))
        run_tracker.start_flow_run("test_flow_id", "test_root_run_id", "test_flow_run_id_1", index=1)
        run_tracker.end_run("test_flow_run_id_1", result={"result": "result"})
        assert len(run_tracker._flow_runs) == 2

        # Start node runs
        run_tracker.start_node_run("node_0", "test_root_run_id", "test_flow_run_id_2", "test_node_run_id_1", index=0)
        run_tracker.end_run("test_node_run_id_1", result={"result": "result"})
        assert len(run_tracker._node_runs) == 1

        status_summary = run_tracker.get_status_summary("test_root_run_id")
        assert status_summary == {
            "__pf__.lines.completed": 1,
            "__pf__.lines.failed": 1,
            "__pf__.nodes.node_0.completed": 1,
        }
