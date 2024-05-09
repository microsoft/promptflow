from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import Mock, patch

import pytest

from promptflow._core._errors import UnexpectedError
from promptflow._proxy import ProxyFactory
from promptflow._proxy._base_executor_proxy import APIBasedExecutorProxy
from promptflow._proxy._csharp_executor_proxy import CSharpExecutorProxy
from promptflow._proxy._python_executor_proxy import PythonExecutorProxy
from promptflow.batch import BatchEngine
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget
from promptflow.executor._errors import GetConnectionError
from promptflow.executor._result import AggregationResult

from ...utils import MemoryRunStorage, get_yaml_file, load_jsonl
from .test_result import get_line_results, get_node_run_infos


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
                GetConnectionError(connection="aoai_conn", node_name="mock", error=Exception("mock")),
                GetConnectionError,
                ErrorTarget.EXECUTOR,
                ["UserError", "ValidationError", "InvalidRequest", "GetConnectionError"],
                "Get connection 'aoai_conn' for node 'mock' error: mock",
            ),
        ],
    )
    def test_batch_engine_run_error(self, side_effect, ex_type, ex_target, ex_codes, ex_msg):
        batch_engine = BatchEngine(get_yaml_file("print_input_flow"))
        with patch("promptflow.batch._batch_engine.BatchEngine._exec_in_task") as mock_func:
            mock_func.side_effect = side_effect
            with patch(
                "promptflow.batch._batch_inputs_processor.BatchInputsProcessor.process_batch_inputs",
                new=Mock(return_value=[]),
            ):
                with pytest.raises(ex_type) as e:
                    batch_engine.run({}, {}, Path("."))
        assert e.value.target == ex_target
        assert e.value.error_codes == ex_codes
        assert e.value.message == ex_msg

    def test_register_executor(self):
        # assert original values
        assert ProxyFactory.executor_proxy_classes["python"] == PythonExecutorProxy
        assert ProxyFactory.executor_proxy_classes["csharp"] == CSharpExecutorProxy

        class MockJSExecutorProxy(APIBasedExecutorProxy):
            pass

        # register new proxy
        ProxyFactory.register_executor("js", MockJSExecutorProxy)
        assert ProxyFactory.executor_proxy_classes["js"] == MockJSExecutorProxy
        assert len(ProxyFactory.executor_proxy_classes) == 3

        # reset to original values
        del ProxyFactory.executor_proxy_classes["js"]

    def test_cancel(self):
        batch_engine = BatchEngine(get_yaml_file("print_input_flow"))
        assert batch_engine._is_canceled is False
        batch_engine.cancel()
        assert batch_engine._is_canceled is True

    def test_persist_run_info(self):
        line_dict = {
            0: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Completed},
            1: {"node_0": Status.Completed, "node_1": Status.Failed, "node_2": Status.Completed},
            2: {"node_0": Status.Completed, "node_1": Status.Completed, "node_2": Status.Bypassed},
        }
        line_results = get_line_results(line_dict)

        mem_run_storge = MemoryRunStorage()
        batch_engine = BatchEngine(get_yaml_file("print_input_flow"), "", storage=mem_run_storge)
        batch_engine._persist_run_info(line_results)

        assert len(mem_run_storge._flow_runs) == 3
        assert len(mem_run_storge._node_runs) == 9

    def test_persist_outputs(self):
        outputs = [
            {"line_number": 0, "output": "Hello World!"},
            {"line_number": 1, "output": "Hello Microsoft!"},
            {"line_number": 2, "output": "Hello Promptflow!"},
        ]
        output_dir = Path(mkdtemp())
        batch_engine = BatchEngine(get_yaml_file("print_input_flow"))
        batch_engine._persist_outputs(outputs, output_dir)
        actual_outputs = load_jsonl(output_dir / "output.jsonl")
        assert actual_outputs == outputs

    def test_update_aggr_result(self):
        output = {"output": "Hello World!"}
        metrics = {"accuracy": 0.9}
        node_run_infos = get_node_run_infos({"aggr_1": Status.Completed, "aggr_2": Status.Completed})
        aggre_result = AggregationResult(output={}, metrics={}, node_run_infos={})
        aggr_exec_result = AggregationResult(output=output, metrics=metrics, node_run_infos=node_run_infos)

        batch_engine = BatchEngine(get_yaml_file("print_input_flow"))
        batch_engine._update_aggr_result(aggre_result, aggr_exec_result)

        assert aggre_result.output == output
        assert aggre_result.metrics == metrics
        assert aggre_result.node_run_infos == node_run_infos
