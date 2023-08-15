import pytest

from promptflow.executor import FlowExecutor
from promptflow.executor.error_codes import InputNotFound, InputTypeError

from ..utils import WRONG_FLOW_ROOT, get_yaml_file


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestValidation:
    @pytest.mark.parametrize(
        "flow_folder, line_input, error_class",
        [
            ("missing_flow_input", {"num11": "22"}, InputNotFound),
            ("input_type_not_parsable", {"num": "hello"}, InputTypeError),
        ],
    )
    def test_input_type_invalid(self, flow_folder, line_input, error_class, dev_connections):
        # case III: Single Node run - the inputs are from flow_inputs + dependency_nodes_outputs
        with pytest.raises(error_class):
            FlowExecutor.load_and_exec_node(
                flow_file=get_yaml_file(flow_folder, WRONG_FLOW_ROOT),
                node_name="stringify_num",
                flow_inputs=line_input,
                dependency_nodes_outputs={},
                connections=dev_connections,
                raise_ex=True,
            )
