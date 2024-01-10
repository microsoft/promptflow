from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from promptflow._core._errors import UnexpectedError
from promptflow.batch import (
    AbstractExecutorProxy,
    APIBasedExecutorProxy,
    BatchEngine,
    CSharpExecutorProxy,
    PythonExecutorProxy,
)
from promptflow.exceptions import ErrorTarget
from promptflow.executor._errors import ConnectionNotFound

from ...utils import get_yaml_file


@pytest.mark.unittest
class TestBatchEngine:
    @pytest.mark.parametrize(
        "side_effect, ex_type, ex_target, ex_codes, ex_msg",
        [
            (
                Exception("test error"),
                UnexpectedError,
                ErrorTarget.BATCH,
                ["SystemError", "UnexpectedError"],
                "Unexpected error occurred while executing the batch run. Error: (Exception) test error.",
            ),
            (
                ConnectionNotFound(message="Connection 'aoai_conn' not found"),
                ConnectionNotFound,
                ErrorTarget.EXECUTOR,
                ["UserError", "ValidationError", "InvalidRequest", "ConnectionNotFound"],
                "Connection 'aoai_conn' not found",
            ),
        ],
    )
    def test_batch_engine_run_error(self, side_effect, ex_type, ex_target, ex_codes, ex_msg):
        batch_engine = BatchEngine(get_yaml_file("print_input_flow"))
        with patch("promptflow.batch._batch_engine.BatchEngine._exec_in_task") as mock_func:
            mock_func.side_effect = side_effect
            with patch(
                "promptflow.batch._batch_inputs_processor.BatchInputsProcessor.process_batch_inputs", new=Mock()
            ):
                with pytest.raises(ex_type) as e:
                    batch_engine.run({}, {}, Path("."))
        assert e.value.target == ex_target
        assert e.value.error_codes == ex_codes
        assert e.value.message == ex_msg

    def test_register_executor(self):
        # assert original values
        assert BatchEngine.executor_proxy_classes["python"] == PythonExecutorProxy
        assert BatchEngine.executor_proxy_classes["csharp"] == CSharpExecutorProxy
        # register new proxy
        BatchEngine.register_executor("python", MockPythonExecutorProxy)
        BatchEngine.register_executor("js", MockJSExecutorProxy)
        assert BatchEngine.executor_proxy_classes["python"] == MockPythonExecutorProxy
        assert BatchEngine.executor_proxy_classes["js"] == MockJSExecutorProxy
        assert len(BatchEngine.executor_proxy_classes) == 3


class MockPythonExecutorProxy(AbstractExecutorProxy):
    pass


class MockJSExecutorProxy(APIBasedExecutorProxy):
    pass
