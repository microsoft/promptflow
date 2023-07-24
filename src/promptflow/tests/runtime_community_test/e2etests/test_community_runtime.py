import os
import uuid

import pytest
from .._utils import get_config_file, read_json_file, assert_run_completed, get_runtime_config

from promptflow._constants import PromptflowEdition
from promptflow.contracts.flow import BatchFlowRequest, Flow
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow.runtime.runtime import PromptFlowRuntime


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
@pytest.mark.community_runtime_test
class TestCommunityRuntime:
    def test_basic_flow(self):
        file_path = get_config_file("flows/environment_variables/flow.json")
        flow = Flow.deserialize(read_json_file(file_path))
        assert flow is not None
        env_key = "abc"
        env_val = "def"
        batch_inputs = [{"env_key": env_key}]
        bfr = BatchFlowRequest(flow=flow, connections={}, batch_inputs=batch_inputs)

        # not setting environment variables should fail
        if env_key in os.environ:
            os.environ.pop(env_key)
        request = SubmitFlowRequest(
            flow_id="environment_variables_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            # flow = flow,
            submission_data=bfr,
            environment_variables={},
        )

        config = get_runtime_config()
        assert config.deployment.edition == PromptflowEdition.COMMUNITY
        runtime = PromptFlowRuntime(config=config)
        result = runtime.execute(request)

        assert result is not None
        assert result["flow_runs"][0]["status"] == "Failed"

        # setting environment variables should success
        if env_key in os.environ:
            os.environ.pop(env_key)
        request = SubmitFlowRequest(
            flow_id="environment_variables_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            # flow = flow,
            submission_data=bfr,
            environment_variables={env_key: env_val},
        )

        runtime = PromptFlowRuntime(get_runtime_config())
        result = runtime.execute(request)
        assert_run_completed(result)
        # assert run["result"]["env_value"][0] == env_val
