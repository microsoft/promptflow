import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor._prompty_executor import PromptyExecutor
from promptflow.executor._result import LineResult

from ...conftest import PROMPTY_FLOW_ROOT


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestPromptyFlow:
    def test_flow_run(self):
        path = PROMPTY_FLOW_ROOT / "prompty_example.prompty"
        executor = PromptyExecutor(flow_file=path)
        line_result = executor.exec_line(inputs={"question": "What is the meaning of life?"}, index=0)
        assert isinstance(line_result, LineResult)
        assert line_result.run_info.status == Status.Completed
        assert isinstance(line_result.output, str)
