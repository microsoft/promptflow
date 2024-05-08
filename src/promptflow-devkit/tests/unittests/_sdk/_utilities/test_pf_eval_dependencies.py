from unittest.mock import patch

import pytest
from promptflow._dependencies._pf_evals import LINE_NUMBER, Local2Cloud, Configuration

DUMMY_TRACE_DESTINATION = ("azureml://subscriptions/sub_id/resourceGroups/resource_group_name"
                     "/providers/Microsoft.MachineLearningServices/workspaces/workspace_name")


@pytest.mark.unittest
class TestPromptflowEvalsDependencies:

    def test_pf_eval_constants_dependencies(self):
        assert LINE_NUMBER == "line_number"
        assert Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME == "instance_results.jsonl"
        assert Local2Cloud.BLOB_ROOT_PROMPTFLOW == "promptflow"
        assert Local2Cloud.BLOB_ARTIFACTS == "PromptFlowArtifacts"

    def test_pf_eval_configuration_dependencies(self):
        with patch("promptflow._sdk._configuration.Configuration._validate", return_value=None):
            config = Configuration(overrides={"trace.destination": DUMMY_TRACE_DESTINATION})
        assert config.get_trace_destination() == DUMMY_TRACE_DESTINATION # noqa: E128
