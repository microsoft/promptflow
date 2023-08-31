import pytest
import yaml

from promptflow.contracts._errors import NodeConditionConflict
from promptflow.contracts.flow import Flow

from ...utils import WRONG_FLOW_ROOT, get_yaml_file


@pytest.mark.unittest
class TestFlow:
    def test_node_condition_conflict(self):
        flow_folder = "node_condition_conflict"
        flow_yaml = get_yaml_file(flow_folder, root=WRONG_FLOW_ROOT)
        with pytest.raises(NodeConditionConflict) as e:
            with open(flow_yaml, "r") as fin:
                Flow.deserialize(yaml.safe_load(fin))
        error_message = "Node 'test_node' can't have both skip and activate condition."
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))
