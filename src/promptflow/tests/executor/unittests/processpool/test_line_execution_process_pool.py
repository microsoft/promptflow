import multiprocessing
import os
import uuid
from multiprocessing import Queue
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
from pytest_mock import MockFixture

from promptflow._utils.logger_utils import LogContext, bulk_logger
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget, UserErrorException
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import (
    LineExecutionProcessPool,
    _exec_line,
    get_multiprocessing_context,
    get_available_max_worker_count
)
from promptflow.executor._result import LineResult

from ...utils import get_flow_sample_inputs, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"


def get_line_inputs(flow_folder=""):
    if flow_folder:
        inputs = get_bulk_inputs(flow_folder)
        return inputs[0]
    return {
        "url": "https://www.microsoft.com/en-us/windows/",
        "text": "some_text",
    }


def get_bulk_inputs(nlinee=4, flow_folder="", sample_inputs_file="", return_dict=False):
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
    return [get_line_inputs() for _ in range(nlinee)]


@pytest.mark.skip("This is a subprocess function used for testing and cannot be tested alone.")
def test_fork_mode_parallelism_in_subprocess(
        dev_connections,
        flow_folder,
        is_set_environ_pf_worker_count,
        pf_worker_count,
        n_process):

    if is_set_environ_pf_worker_count:
        os.environ["PF_WORKER_COUNT"] = pf_worker_count
    executor = FlowExecutor.create(
        get_yaml_file(flow_folder),
        dev_connections,
    )
    run_id = str(uuid.uuid4())
    bulk_inputs = get_bulk_inputs()
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
                mock_logger.info.assert_any_call(
                    f"Process count set to {pf_worker_count} based on 'PF_WORKER_COUNT' environment variable.")
            else:
                mock_logger.info.assert_any_call("Using fork to create new process")
                mock_logger.info.assert_any_call(
                    f"Calculated process count ({n_process}) by taking the minimum value among the the "
                    f"default value for worker_count ({pool._worker_count}) and the row count ({nlines})"
                )


@pytest.mark.skip("This is a subprocess function used for testing and cannot be tested alone.")
def test_spawn_mode_parallelism_in_subprocess(
        dev_connections,
        flow_folder,
        is_set_environ_pf_worker_count,
        is_calculation_smaller_than_set,
        pf_worker_count,
        estimated_available_worker_count,
        n_process
):
    os.environ["PF_BATCH_METHOD"] = "spawn"
    if is_set_environ_pf_worker_count:
        os.environ["PF_WORKER_COUNT"] = pf_worker_count
    executor = FlowExecutor.create(
        get_yaml_file(flow_folder),
        dev_connections,
    )
    run_id = str(uuid.uuid4())
    bulk_inputs = get_bulk_inputs()
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
                        mock_logger.info.assert_any_call(
                            f"Process count set to {pf_worker_count} based on 'PF_WORKER_COUNT' environment variable.")
                        mock_logger.warning.assert_any_call(
                            f"The estimated available worker count calculated based on the system available memory "
                            f"is {estimated_available_worker_count}, but the PF_WORKER_COUNT is set to "
                            f"{pf_worker_count}. This may affect optimal memory usage and performance. ")
                    elif is_set_environ_pf_worker_count and not is_calculation_smaller_than_set:
                        mock_logger.info.assert_any_call(
                            f"Process count set to {pf_worker_count} based on 'PF_WORKER_COUNT' environment variable.")
                    elif not is_set_environ_pf_worker_count:
                        mock_logger.info.assert_any_call("Not using fork to create new process")
                        mock_logger.info.assert_any_call(
                            "The environment variable PF_WORKER_COUNT is not set or invalid. Calculate the worker "
                            "count based on the currently memory usage"
                        )
                        mock_logger.info.assert_any_call(
                            f"Calculated process count ({n_process}) by taking the minimum value among estimated "
                            f"process count ({estimated_available_worker_count}), the row count ({nlines}) and the "
                            f"default worker count ({pool._worker_count})."
                        )


@pytest.mark.unittest
class TestLineExecutionProcessPool:
    def create_line_execution_process_pool(self, dev_connections):
        executor = FlowExecutor.create(
            get_yaml_file(SAMPLE_FLOW),
            dev_connections,
            line_timeout_sec=1,
        )
        run_id = str(uuid.uuid4())
        bulk_inputs = get_bulk_inputs()
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
            bulk_inputs = get_bulk_inputs()
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
        bulk_inputs = get_bulk_inputs()
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
        line_inputs = get_line_inputs()
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
            line_inputs = get_line_inputs()
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
        bulk_inputs = get_bulk_inputs()
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
        p = multiprocessing.Process(
            target=test_fork_mode_parallelism_in_subprocess,
            args=(dev_connections,
                  flow_folder,
                  is_set_environ_pf_worker_count,
                  pf_worker_count,
                  n_process))
        p.start()
        p.join()
        assert p.exitcode == 0

    @pytest.mark.parametrize(
        (
            "flow_folder",
            "is_set_environ_pf_worker_count",
            "is_calculation_smaller_than_set",
            "pf_worker_count",
            "estimated_available_worker_count",
            "n_process"
        ),
        [
            (SAMPLE_FLOW, True, False, "2", 4, 2),
            (SAMPLE_FLOW, True, True, "6", 2, 6),
            (SAMPLE_FLOW, False, True, None, 2, 2)
        ],
    )
    def test_process_pool_parallelism_in_non_spawn_mode(
        self,
        dev_connections,
        flow_folder,
        is_set_environ_pf_worker_count,
        is_calculation_smaller_than_set,
        pf_worker_count,
        estimated_available_worker_count,
        n_process
    ):
        p = multiprocessing.Process(
            target=test_spawn_mode_parallelism_in_subprocess,
            args=(dev_connections,
                  flow_folder,
                  is_set_environ_pf_worker_count,
                  is_calculation_smaller_than_set,
                  pf_worker_count,
                  estimated_available_worker_count,
                  n_process))
        p.start()
        p.join()
        assert p.exitcode == 0

    @pytest.mark.parametrize("env_var, expected_use_default, expected_worker_count", [
        ({}, True, 16),
        ({'PF_WORKER_COUNT': '5'}, False, 5),
        ({'PF_WORKER_COUNT': 'invalid'}, True, 16),
        ({'PF_WORKER_COUNT': '0'}, True, 16)
    ])
    def test_worker_count_setting(self, dev_connections, env_var, expected_use_default, expected_worker_count):
        with patch.dict(os.environ, env_var), patch.object(bulk_logger, 'warning') as mock_warning:
            line_execution_process_pool = self.create_line_execution_process_pool(dev_connections)

            if 'invalid' in env_var.get('PF_WORKER_COUNT', '') or '0' in env_var.get('PF_WORKER_COUNT', ''):
                mock_warning.assert_called()

            assert line_execution_process_pool._use_default_worker_count == expected_use_default
            assert line_execution_process_pool._worker_count == expected_worker_count


class TestGetAvailableMaxWorkerCount:
    @pytest.mark.parametrize(
        "available_memory, process_memory, expected_max_worker_count, actual_calculate_worker_count",
        [
            (128.0, 64.0, 2, 2.0),  # available_memory/process_memory > 1
            (63.0, 64.0, 1, 1),   # available_memory/process_memory < 1
        ],
    )
    def test_get_available_max_worker_count(
        self, available_memory, process_memory, expected_max_worker_count, actual_calculate_worker_count
    ):
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value.available = available_memory * 1024 * 1024
            with patch("psutil.Process") as mock_process:
                mock_process.return_value.memory_info.return_value.rss = process_memory * 1024 * 1024
                with patch("promptflow.executor._line_execution_process_pool.bulk_logger") as mock_logger:
                    mock_logger.warning.return_value = None
                    estimated_available_worker_count = get_available_max_worker_count()
                    assert estimated_available_worker_count == expected_max_worker_count
                    if actual_calculate_worker_count < 1:
                        mock_logger.warning.assert_called_with(
                            f"Available max worker count {actual_calculate_worker_count} is less than 1, "
                            "set it to 1."
                        )
                    mock_logger.info.assert_called_with(
                        f"Current system's available memory is {available_memory}MB, "
                        f"memory consumption of current process is {process_memory}MB, "
                        f"estimated available worker count is {available_memory}/{process_memory} "
                        f"= {actual_calculate_worker_count}"
                    )
