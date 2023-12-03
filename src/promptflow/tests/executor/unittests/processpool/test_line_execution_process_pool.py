import multiprocessing
import os
import uuid
from multiprocessing import Queue
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
from pytest_mock import MockFixture

from promptflow._utils.logger_utils import LogContext
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget, UserErrorException
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import (
    LineExecutionProcessPool,
    _exec_line,
    get_multiprocessing_context,
)
from promptflow.executor._result import LineResult

from ...utils import get_flow_sample_inputs, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"


@pytest.mark.unittest
class TestLineExecutionProcessPool:
    def get_line_inputs(self, flow_folder=""):
        if flow_folder:
            inputs = self.get_bulk_inputs(flow_folder)
            return inputs[0]
        return {
            "url": "https://www.microsoft.com/en-us/windows/",
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

    def create_line_execution_process_pool(self, dev_connections):
        executor = FlowExecutor.create(
            get_yaml_file(SAMPLE_FLOW),
            dev_connections,
            line_timeout_sec=1,
        )
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)
        line_execution_process_pool = LineExecutionProcessPool(
            executor,
            nlines,
            run_id,
            "",
            False,
            None,
        )
        return line_execution_process_pool

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
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_exec_line_failed_when_line_execution_not_start(self, flow_folder, dev_connections, mocker: MockFixture):
        output_queue = Queue()
        executor = FlowExecutor.create(
            get_yaml_file(flow_folder),
            dev_connections,
            line_timeout_sec=1,
        )
        test_error_msg = "Test user error"
        with patch("promptflow.executor.flow_executor.FlowExecutor.exec_line", autouse=True) as mock_exec_line:
            mock_exec_line.side_effect = UserErrorException(
                message=test_error_msg, target=ErrorTarget.AZURE_RUN_STORAGE
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
            assert line_result.run_info.error["message"] == test_error_msg
            assert line_result.run_info.error["code"] == "UserError"
            assert line_result.run_info.status == Status.Failed

    def test_process_set_environment_variable_successed(self, dev_connections):
        os.environ["PF_BATCH_METHOD"] = "spawn"
        line_execution_process_pool = self.create_line_execution_process_pool(dev_connections)
        use_fork = line_execution_process_pool._use_fork
        assert use_fork is False

    def test_process_set_environment_variable_failed(self, dev_connections):
        with patch("promptflow.executor._line_execution_process_pool.bulk_logger") as mock_logger:
            mock_logger.warning.return_value = None
            os.environ["PF_BATCH_METHOD"] = "test"
            line_execution_process_pool = self.create_line_execution_process_pool(dev_connections)
            use_fork = line_execution_process_pool._use_fork
            assert use_fork == (multiprocessing.get_start_method() == "fork")
            sys_start_methods = multiprocessing.get_all_start_methods()
            exexpected_log_message = (
                "Failed to set start method to 'test', start method test" f" is not in: {sys_start_methods}."
            )
            mock_logger.warning.assert_called_once_with(exexpected_log_message)

    def test_process_not_set_environment_variable(self, dev_connections):
        line_execution_process_pool = self.create_line_execution_process_pool(dev_connections)
        use_fork = line_execution_process_pool._use_fork
        assert use_fork == (multiprocessing.get_start_method() == "fork")

    def test_get_multiprocessing_context(self):
        # Set default start method to spawn
        context = get_multiprocessing_context("spawn")
        assert context.get_start_method() == "spawn"
        # Not set start method
        context = get_multiprocessing_context()
        assert context.get_start_method() == multiprocessing.get_start_method()

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_process_pool_run_with_exception(self, flow_folder, dev_connections, mocker: MockFixture):
        # mock process pool run execution raise error
        test_error_msg = "Test user error"
        mocker.patch(
            "promptflow.executor._line_execution_process_pool.LineExecutionProcessPool." "_timeout_process_wrapper",
            side_effect=UserErrorException(message=test_error_msg, target=ErrorTarget.AZURE_RUN_STORAGE),
        )
        executor = FlowExecutor.create(
            get_yaml_file(flow_folder),
            dev_connections,
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
            with pytest.raises(UserErrorException) as e:
                pool.run(zip(range(nlines), bulk_inputs))
            assert e.value.message == test_error_msg
            assert e.value.target == ErrorTarget.AZURE_RUN_STORAGE
            assert e.value.error_codes[0] == "UserError"

    @pytest.mark.parametrize(
        (
            "flow_folder",
            "is_set_environ_pf_worker_count",
            "pf_worker_count",
            "n_process"
        ),
        [
            (SAMPLE_FLOW, True, "3", 3),
            (SAMPLE_FLOW, False, None, 4)
        ],
    )
    def test_process_pool_parallelism_in_fork_mode(
            self,
            dev_connections,
            flow_folder,
            is_set_environ_pf_worker_count,
            pf_worker_count,
            n_process):
        os.environ.pop("PF_WORKER_COUNT", None)  # Delete the environment variable if it exists
        if is_set_environ_pf_worker_count:
            os.environ["PF_WORKER_COUNT"] = pf_worker_count
        executor = FlowExecutor.create(
            get_yaml_file(flow_folder),
            dev_connections,
        )
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)

        with patch("promptflow.executor._line_execution_process_pool.bulk_logger") as mock_logger:
            with LineExecutionProcessPool(
                executor,
                nlines,
                run_id,
                "",
                False,
                None,
            ) as pool:
                assert pool._n_process == n_process
                if is_set_environ_pf_worker_count:
                    mock_logger.info.assert_called_with(
                        f"PF_WORKER_COUNT:{pf_worker_count}, process count: {n_process}")
                else:
                    mock_logger.info.assert_called_with(
                        f"Using fork, and the environment variable PF_WORKER_COUNT is not set. The number of processes "
                        f"is determined by the lesser of the default value for worker_count "
                        f"{pool._DEFAULT_WORKER_COUNT} and the row count: {nlines}. process count: {n_process}")

    @pytest.mark.parametrize(
        (
            "flow_folder",
            "is_set_environ_pf_worker_count",
            "is_calculation_smaller_than_set",
            "pf_worker_count",
            "available_max_worker_count",
            "n_process"
        ),
        [
            (SAMPLE_FLOW, True, False, "2", 4, 2),
            (SAMPLE_FLOW, True, True, "6", 2, 6),
            (SAMPLE_FLOW, False, True, None, 2, 2)
        ],
    )
    def test_process_pool_parallelism_in_non_fork_mode(
        self,
        dev_connections,
        flow_folder,
        is_set_environ_pf_worker_count,
        is_calculation_smaller_than_set,
        pf_worker_count,
        available_max_worker_count,
        n_process
    ):
        os.environ.pop("PF_WORKER_COUNT", None)  # Delete the environment variable if it exists
        os.environ["PF_BATCH_METHOD"] = "spawn"
        if is_set_environ_pf_worker_count:
            os.environ["PF_WORKER_COUNT"] = pf_worker_count
        executor = FlowExecutor.create(
            get_yaml_file(flow_folder),
            dev_connections,
        )
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)

        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value.available = 128.0 * 1024 * 1024
            with patch("psutil.Process") as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 64 * 1024 * 1024
                with patch("promptflow.executor._line_execution_process_pool.bulk_logger") as mock_logger:
                    with LineExecutionProcessPool(
                        executor,
                        nlines,
                        run_id,
                        "",
                        False,
                        None,
                    ) as pool:
                        assert pool._n_process == n_process
                        if is_set_environ_pf_worker_count and is_calculation_smaller_than_set:
                            mock_logger.warning.assert_called_with(
                                f"The maximum number of processes calculated based on the system available memory "
                                f"is {available_max_worker_count}, and the PF_WORKER_COUNT is set to {pf_worker_count}"
                                f". Use the PF_WORKER_COUNT:{pf_worker_count} as the final number of processes. "
                                f"process count: {n_process}")
                        elif is_set_environ_pf_worker_count and not is_calculation_smaller_than_set:
                            mock_logger.info.assert_called_with(
                                f"PF_WORKER_COUNT:{pf_worker_count}, process count: {n_process}")
                        elif not is_set_environ_pf_worker_count:
                            mock_logger.info.assert_called_with(
                                f"Not using fork, and the environment variable PF_WORKER_COUNT is not set. Calculate "
                                f"the current system available memory divided by process memory, and take the minimum "
                                f"value of this value: {available_max_worker_count}, the default value for worker_count"
                                f": {pool._DEFAULT_WORKER_COUNT} and the row count: {nlines} as the final number of "
                                f"processes. process count: {n_process}")
