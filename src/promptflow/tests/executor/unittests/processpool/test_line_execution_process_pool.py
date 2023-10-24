import sys
import uuid
from multiprocessing import Queue
from pathlib import Path
from tempfile import mkdtemp

import pytest
from pytest_mock import MockFixture

from promptflow._utils.logger_utils import LogContext
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import LineExecutionProcessPool, _exec_line
from promptflow.executor.flow_executor import LineResult

from ...utils import FLOW_ROOT, get_flow_sample_inputs, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"


@pytest.mark.unittest
class TestLineExecutionProcessPool:
    def get_line_inputs(self, flow_folder=""):
        if flow_folder:
            inputs = self.get_bulk_inputs(flow_folder)
            return inputs[0]
        return {
            "url": "https://www.apple.com/shop/buy-iphone/iphone-14",
            "text": "some_text",
        }

    def get_bulk_inputs(self, nlinee=4, flow_folder="", sample_inputs_file="", return_dict=False):
        if flow_folder:
            if not sample_inputs_file:
                sample_inputs_file = "samples.json"
            inputs = get_flow_sample_inputs(flow_folder, sample_inputs_file=sample_inputs_file)
            if isinstance(inputs, list) and len(inputs) > 0:
                return inputs
            elif isinstance(inputs, dict):
                if return_dict:
                    return inputs
                return [inputs]
            else:
                raise Exception(f"Invalid type of bulk input: {inputs}")
        return [self.get_line_inputs() for _ in range(nlinee)]

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_line_execution_process_pool(self, flow_folder, dev_connections):
        log_path = str(Path(mkdtemp()) / "test.log")
        log_context_initializer = LogContext(log_path).get_initializer()
        log_context = log_context_initializer()
        with log_context:
            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
            executor._log_interval = 1
            run_id = str(uuid.uuid4())
            bulk_inputs = self.get_bulk_inputs()
            nlines = len(bulk_inputs)
            run_id = run_id or str(uuid.uuid4())
            with LineExecutionProcessPool(
                executor,
                nlines,
                run_id,
                "",
                False,
                None,
            ) as pool:
                result_list = pool.run(zip(range(nlines), bulk_inputs))
            assert len(result_list) == nlines
            for i, line_result in enumerate(result_list):
                assert isinstance(line_result, LineResult)
                assert line_result.run_info.status == Status.Completed, f"{i}th line got {line_result.run_info.status}"

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_line_execution_not_completed(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(
            get_yaml_file(flow_folder),
            dev_connections,
            line_timeout_sec=1,
        )
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)
        with LineExecutionProcessPool(
            executor,
            nlines,
            run_id,
            "",
            False,
            None,
        ) as pool:
            result_list = pool.run(zip(range(nlines), bulk_inputs))
            result_list = sorted(result_list, key=lambda r: r.run_info.index)
        assert len(result_list) == nlines
        for i, line_result in enumerate(result_list):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.error["message"] == f"Line {i} execution timeout for exceeding 1 seconds"
            assert line_result.run_info.error["code"] == "UserError"
            assert line_result.run_info.status == Status.Failed

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_exec_line(self, flow_folder, dev_connections, mocker: MockFixture):
        output_queue = Queue()
        executor = FlowExecutor.create(
            get_yaml_file(flow_folder),
            dev_connections,
            line_timeout_sec=1,
        )
        run_id = str(uuid.uuid4())
        line_inputs = self.get_line_inputs()
        line_result = _exec_line(
            executor=executor,
            output_queue=output_queue,
            inputs=line_inputs,
            run_id=run_id,
            index=0,
            variant_id="",
            validate_inputs=False,
        )
        assert isinstance(line_result, LineResult)

    @pytest.mark.parametrize(
        "flow_folder, batch_input, error_message, error_class",
        [
            (
                "simple_flow_with_python_tool",
                [{"num11": "22"}],
                (
                    "The value for flow input 'num' is not provided in line 0 of input data. "
                    "Please review your input data or remove this input in your flow if it's no longer needed."
                ),
                "InputNotFound",
            )
        ],
    )
    def test_exec_line_with_exception(self, flow_folder, batch_input, error_message, error_class, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        executor.exec_bulk(
            batch_input,
        )
        output_queue = Queue()
        run_id = str(uuid.uuid4())
        line_result = _exec_line(
            executor=executor,
            output_queue=output_queue,
            inputs=batch_input[0],
            run_id=run_id,
            index=0,
            variant_id="",
            validate_inputs=False,
        )
        if (
            (sys.version_info.major == 3)
            and (sys.version_info.minor >= 11)
            and ((sys.platform == "linux") or (sys.platform == "darwin"))
        ):
            # Python >= 3.11 has a different error message on linux and macos
            error_message_compare = error_message.replace("int", "ValueType.INT")
            assert error_message_compare in str(
                line_result.run_info.error
            ), f"Expected message {error_message_compare} but got {str(line_result.run_info.error)}"
        else:
            assert error_message in str(
                line_result.run_info.error
            ), f"Expected message {error_message} but got {str(line_result.run_info.error)}"
        assert error_class in str(
            line_result.run_info.error
        ), f"Expected message {error_class} but got {str(line_result.run_info.error)}"
