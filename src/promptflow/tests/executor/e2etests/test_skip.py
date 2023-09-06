import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor._errors import ReferenceNodeBypassed
from promptflow.executor.flow_executor import FlowExecutor, LineResult

from ..utils import WRONG_FLOW_ROOT, get_flow_inputs, get_yaml_file


@pytest.mark.e2etest
class TestExecutorSkip:
    def test_skip(self):
        flow_folder = "conditional_flow_with_skip"
        executor = FlowExecutor.create(get_yaml_file(flow_folder), connections={})
        results = executor.exec_line(get_flow_inputs(flow_folder))
        self.assert_skip_flow_result(results)

    def test_skip_wrong_flow(self):
        flow_folder = "skip_is_bypassed"
        executor = FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT), connections={})
        with pytest.raises(ReferenceNodeBypassed) as e:
            executor.exec_line(get_flow_inputs(flow_folder, WRONG_FLOW_ROOT))
        error_message = (
            "Invalid node reference: The node node_b referenced by node_c has been bypassed, "
            "so the value of this node cannot be returned. Please refer to the node that will "
            "not be bypassed as the default return value."
        )
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))

    def assert_skip_flow_result(self, result: LineResult):
        # Validate the flow status
        assert result.run_info.status == Status.Completed
        # Validate the flow output
        assert isinstance(result.output, dict)
        assert result.output == {"string": "Result: 10 is even number, skip the next node"}
        # Validate the flow node run infos
        assert len(result.node_run_infos) == 3

        node_run_info = result.node_run_infos["is_even"]
        assert node_run_info.status == Status.Completed
        assert node_run_info.output == {"is_even": True, "message": "10 is even number, skip the next node"}

        node_run_info = result.node_run_infos["conditional_node"]
        assert node_run_info.status == Status.Bypassed
        assert node_run_info.output == "10 is even number, skip the next node"

        node_run_info = result.node_run_infos["print_result"]
        assert node_run_info.status == Status.Completed
        assert node_run_info.output == "Result: 10 is even number, skip the next node"
