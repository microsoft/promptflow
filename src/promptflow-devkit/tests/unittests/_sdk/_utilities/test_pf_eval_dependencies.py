import pytest
from promptflow._dependencies._pf_evals import _get_pf_evals_dependencies


@pytest.mark.unittest
class TestPromptflowEvalsDependencies:

    def test_pf_eval_dependencies(self):
        result = _get_pf_evals_dependencies()
        assert result["LINE_NUMBER"] == "line_number"
        assert result["Local2Cloud"].FLOW_INSTANCE_RESULTS_FILE_NAME == "instance_results.jsonl"
        assert result["Local2Cloud"].BLOB_ROOT_PROMPTFLOW == "promptflow"
        assert result["Local2Cloud"].BLOB_ARTIFACTS == "PromptFlowArtifacts"
