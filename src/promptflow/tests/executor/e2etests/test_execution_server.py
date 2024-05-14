import math
import sys

import pytest
from fastapi.testclient import TestClient

from promptflow.executor._result import LineResult

from ..utils import construct_flow_execution_request_json


@pytest.mark.e2etest
class TestExecutionServer:
    # region /execution
    @pytest.mark.skipif(sys.platform != "win32", reason="The test will fail on linux and investigate later.")
    def test_execution_flow_with_nan_inf(self, executor_client: TestClient):
        flow_execution_request = construct_flow_execution_request_json(
            flow_folder="flow-with-nan-inf", inputs={"number": 1}
        )
        response = executor_client.post(url="/execution/flow", json=flow_execution_request)
        assert response.status_code == 200, f"response: {response.json()}"
        line_result = LineResult.deserialize(response.json())
        output = line_result.output["output"]
        assert math.isnan(output["nan"])
        assert math.isinf(output["inf"])

    # endregion
