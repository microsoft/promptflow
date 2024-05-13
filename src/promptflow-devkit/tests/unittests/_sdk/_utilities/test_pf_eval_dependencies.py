from unittest.mock import patch

import pytest

from promptflow._dependencies._pf_evals import LINE_NUMBER, Local2Cloud, get_trace_destination
from promptflow._sdk._pf_client import PFClient

DUMMY_TRACE_DESTINATION = (
    "azureml://subscriptions/sub_id/resourceGroups/resource_group_name"
    "/providers/Microsoft.MachineLearningServices/workspaces/workspace_name"
)


@pytest.fixture
def patch_config_validation():
    with patch("promptflow._sdk._configuration.Configuration._validate", return_value=None):
        yield


@pytest.mark.unittest
class TestPromptflowEvalsDependencies:
    def test_pf_eval_constants_dependencies(self):
        assert LINE_NUMBER == "line_number"
        assert Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME == "instance_results.jsonl"
        assert Local2Cloud.BLOB_ROOT_PROMPTFLOW == "promptflow"
        assert Local2Cloud.BLOB_ARTIFACTS == "PromptFlowArtifacts"

    def test_pf_eval_configuration_dependencies(self, patch_config_validation):
        pf_client = PFClient(config={"trace.destination": DUMMY_TRACE_DESTINATION})
        assert get_trace_destination(pf_client=pf_client) == DUMMY_TRACE_DESTINATION
