import asyncio
import glob
import multiprocessing
import os
import traceback
import uuid
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._constants import OUTPUT_FILE_NAME
from promptflow._proxy._chat_group_orchestrator_proxy import ChatGroupOrchestratorProxy
from promptflow._proxy._proxy_factory import ProxyFactory
from promptflow._proxy._python_executor_proxy import PythonExecutorProxy
from promptflow._sdk.entities._chat_group._chat_role import ChatRole
from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.utils import dump_list_to_jsonl
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._errors import EmptyInputsData
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status
from promptflow.executor._errors import InputNotFound

from ..conftest import setup_recording
from ..process_utils import MockForkServerProcess, MockSpawnProcess, override_process_class
from ..single_line_python_executor_proxy import SingleLinePythonExecutorProxy
from ..utils import (
    MemoryRunStorage,
    get_batch_inputs_line,
    get_flow_expected_metrics,
    get_flow_expected_status_summary,
    get_flow_folder,
    get_flow_inputs_file,
    get_yaml_file,
    load_jsonl,
    submit_batch_run,
)

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"

TEST_ROOT = Path(__file__).parent.parent.parent
RUNS_ROOT = TEST_ROOT / "test_configs/runs"


async def async_submit_batch_run(flow_folder, inputs_mapping, connections):
    batch_result = submit_batch_run(flow_folder, inputs_mapping, connections=connections)
    await asyncio.sleep(1)
    return batch_result


def run_batch_with_start_method(
    multiprocessing_start_method,
    flow_folder,
    inputs_mapping,
    dev_connections,
    exception_queue,
):
    try:
        _run_batch_with_start_method(multiprocessing_start_method, flow_folder, inputs_mapping, dev_connections)
    except BaseException as e:
        msg = f"Hit exception: {e}\nStack trace: {traceback.format_exc()}"
        print(msg)
        exception_queue.put(Exception(msg))
        raise


def _run_batch_with_start_method(multiprocessing_start_method, flow_folder, inputs_mapping, dev_connections):
    os.environ["PF_BATCH_METHOD"] = multiprocessing_start_method
    batch_result, output_dir = submit_batch_run(
        flow_folder, inputs_mapping, connections=dev_connections, return_output_dir=True
    )
    # The method is used as start method to construct new process in tests.
    # We need to make sure the necessary setup in place to get pass along in new process
    process_class_dict = {"spawn": MockSpawnProcess, "forkserver": MockForkServerProcess}
    override_process_class(process_class_dict)

    # recording injection again since this method is running in a new process
    setup_recording()

    assert isinstance(batch_result, BatchResult)
    nlines = get_batch_inputs_line(flow_folder)
    assert batch_result.total_lines == nlines
    assert batch_result.completed_lines == nlines
    assert batch_result.start_time < batch_result.end_time
    assert batch_result.system_metrics.duration > 0

    outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
    assert len(outputs) == nlines
    for i, output in enumerate(outputs):
        assert isinstance(output, dict)
        assert "line_number" in output, f"line_number is not in {i}th output {output}"
        assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"


class MockRun(object):
    def __init__(self, name: str, output_path: Path):
        self.name = name
        self._output_path = output_path
        self.data = None
        self._run_source = None
        self.flow = None


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestBatch:
    def test_batch_storage(self, dev_connections):
        mem_run_storage = MemoryRunStorage()
        run_id = str(uuid.uuid4())
        inputs_mapping = {"url": "${data.url}"}
        batch_result = submit_batch_run(
            SAMPLE_FLOW, inputs_mapping, run_id=run_id, connections=dev_connections, storage=mem_run_storage
        )

        nlines = get_batch_inputs_line(SAMPLE_FLOW)
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == nlines
        assert len(mem_run_storage._flow_runs) == nlines
        assert all(flow_run_info.status == Status.Completed for flow_run_info in mem_run_storage._flow_runs.values())
        assert all(node_run_info.status == Status.Completed for node_run_info in mem_run_storage._node_runs.values())

    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping",
        [
            (
                SAMPLE_FLOW,
                {"url": "${data.url}"},
            ),
            (
                "prompt_tools",
                {"text": "${data.text}"},
            ),
            (
                "script_with___file__",
                {"text": "${data.text}"},
            ),
            (
                "sample_flow_with_functions",
                {"question": "${data.question}"},
            ),
        ],
    )
    def test_batch_run(self, flow_folder, inputs_mapping, dev_connections):
        batch_result, output_dir = submit_batch_run(
            flow_folder, inputs_mapping, connections=dev_connections, return_output_dir=True
        )

        assert isinstance(batch_result, BatchResult)
        nlines = get_batch_inputs_line(flow_folder)
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == nlines
        assert batch_result.start_time < batch_result.end_time
        assert batch_result.system_metrics.duration > 0

        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == nlines
        for i, output in enumerate(outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"

    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping",
        [
            (
                SAMPLE_FLOW,
                {"url": "${data.url}"},
            ),
            (
                "prompt_tools",
                {"text": "${data.text}"},
            ),
            (
                "script_with___file__",
                {"text": "${data.text}"},
            ),
            (
                "sample_flow_with_functions",
                {"question": "${data.question}"},
            ),
        ],
    )
    def test_spawn_mode_batch_run(self, flow_folder, inputs_mapping, dev_connections):
        if "spawn" not in multiprocessing.get_all_start_methods():
            pytest.skip("Unsupported start method: spawn")
        exception_queue = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=run_batch_with_start_method,
            args=("spawn", flow_folder, inputs_mapping, dev_connections, exception_queue),
        )
        p.start()
        p.join()
        if p.exitcode != 0:
            ex = exception_queue.get(timeout=1)
            raise ex

    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping",
        [
            (
                SAMPLE_FLOW,
                {"url": "${data.url}"},
            ),
            (
                "prompt_tools",
                {"text": "${data.text}"},
            ),
            (
                "script_with___file__",
                {"text": "${data.text}"},
            ),
            (
                "sample_flow_with_functions",
                {"question": "${data.question}"},
            ),
        ],
    )
    def test_forkserver_mode_batch_run(self, flow_folder, inputs_mapping, dev_connections):
        if "forkserver" not in multiprocessing.get_all_start_methods():
            pytest.skip("Unsupported start method: forkserver")
        exception_queue = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=run_batch_with_start_method,
            args=("forkserver", flow_folder, inputs_mapping, dev_connections, exception_queue),
        )
        p.start()
        p.join()
        if p.exitcode != 0:
            ex = exception_queue.get(timeout=1)
            raise ex

    def test_batch_run_then_eval(self, dev_connections):
        batch_resutls, output_dir = submit_batch_run(
            SAMPLE_FLOW, {"url": "${data.url}"}, connections=dev_connections, return_output_dir=True
        )
        nlines = get_batch_inputs_line(SAMPLE_FLOW)
        assert batch_resutls.completed_lines == nlines

        input_dirs = {"data": get_flow_inputs_file(SAMPLE_FLOW, file_name="samples.json"), "run.outputs": output_dir}
        inputs_mapping = {
            "variant_id": "baseline",
            "groundtruth": "${data.url}",
            "prediction": "${run.outputs.category}",
        }
        eval_result = submit_batch_run(SAMPLE_EVAL_FLOW, inputs_mapping, input_dirs=input_dirs)
        assert eval_result.completed_lines == nlines, f"Only returned {eval_result.completed_lines}/{nlines} outputs."
        assert len(eval_result.metrics) > 0, "No metrics are returned."
        assert eval_result.metrics["accuracy"] == 0, f"Accuracy should be 0, got {eval_result.metrics}."

    def test_batch_with_metrics(self, dev_connections):
        flow_folder = SAMPLE_EVAL_FLOW
        inputs_mapping = {
            "variant_id": "${data.variant_id}",
            "groundtruth": "${data.groundtruth}",
            "prediction": "${data.prediction}",
        }
        batch_results = submit_batch_run(flow_folder, inputs_mapping, connections=dev_connections)
        assert isinstance(batch_results, BatchResult)
        assert isinstance(batch_results.metrics, dict)
        assert batch_results.metrics == get_flow_expected_metrics(flow_folder)
        assert batch_results.total_lines == batch_results.completed_lines
        assert batch_results.node_status == get_flow_expected_status_summary(flow_folder)

    def test_batch_with_partial_failure(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        inputs_mapping = {"idx": "${data.idx}", "mod": "${data.mod}", "mod_2": "${data.mod_2}"}
        batch_results = submit_batch_run(flow_folder, inputs_mapping, connections=dev_connections)
        assert isinstance(batch_results, BatchResult)
        assert batch_results.total_lines == 10
        assert batch_results.completed_lines == 5
        assert batch_results.failed_lines == 5
        assert batch_results.node_status == get_flow_expected_status_summary(flow_folder)

    def test_batch_with_line_number(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        input_dirs = {"data": "inputs/data.jsonl", "output": "inputs/output.jsonl"}
        inputs_mapping = {"idx": "${output.idx}", "mod": "${data.mod}", "mod_2": "${data.mod_2}"}
        batch_results, output_dir = submit_batch_run(
            flow_folder, inputs_mapping, input_dirs=input_dirs, connections=dev_connections, return_output_dir=True
        )
        assert isinstance(batch_results, BatchResult)
        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == 2
        assert outputs == [
            {"line_number": 0, "output": 1},
            {"line_number": 6, "output": 7},
        ]

    def test_batch_with_openai_metrics(self, dev_connections):
        inputs_mapping = {"url": "${data.url}"}
        batch_result, output_dir = submit_batch_run(
            SAMPLE_FLOW, inputs_mapping, connections=dev_connections, return_output_dir=True
        )
        nlines = get_batch_inputs_line(SAMPLE_FLOW)
        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == nlines
        assert batch_result.system_metrics.total_tokens > 0
        assert batch_result.system_metrics.prompt_tokens > 0
        assert batch_result.system_metrics.completion_tokens > 0

    def test_batch_with_default_input(self):
        mem_run_storage = MemoryRunStorage()
        default_input_value = "input value from default"
        inputs_mapping = {"text": "${data.text}"}
        batch_result, output_dir = submit_batch_run(
            "default_input", inputs_mapping, storage=mem_run_storage, return_output_dir=True
        )
        assert batch_result.total_lines == batch_result.completed_lines

        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == 1
        assert outputs[0]["output"] == default_input_value
        assert all(
            node_run_info.status == Status.Completed and node_run_info.output == [default_input_value]
            for node_run_info in mem_run_storage._node_runs.values()
            if node_run_info.node == "aggregate_node"
        )

    @pytest.mark.parametrize(
        "flow_folder, batch_input, expected_type",
        [
            ("simple_aggregation", [{"text": 4}], str),
            ("simple_aggregation", [{"text": 4.5}], str),
            ("simple_aggregation", [{"text": "3.0"}], str),
        ],
    )
    def test_batch_run_line_result(self, flow_folder, batch_input, expected_type):
        mem_run_storage = MemoryRunStorage()
        input_file = Path(mkdtemp()) / "inputs.jsonl"
        dump_list_to_jsonl(input_file, batch_input)
        input_dirs = {"data": input_file}
        inputs_mapping = {"text": "${data.text}"}
        batch_results = submit_batch_run(flow_folder, inputs_mapping, input_dirs=input_dirs, storage=mem_run_storage)
        assert isinstance(batch_results, BatchResult)
        assert all(
            type(flow_run_info.inputs["text"]) is expected_type for flow_run_info in mem_run_storage._flow_runs.values()
        )

    @pytest.mark.parametrize(
        "flow_folder, input_mapping, error_class, error_message",
        [
            (
                "connection_as_input",
                {},
                InputNotFound,
                "The input for flow cannot be empty in batch mode. Please review your flow and provide valid inputs.",
            ),
            (
                "script_with___file__",
                {"text": "${data.text}"},
                EmptyInputsData,
                "Couldn't find any inputs data at the given input paths. Please review the provided path "
                "and consider resubmitting.",
            ),
        ],
    )
    def test_batch_run_failure(self, flow_folder, input_mapping, error_class, error_message):
        with pytest.raises(error_class) as e:
            submit_batch_run(flow_folder, input_mapping, input_file_name="empty_inputs.jsonl")
        assert error_message in e.value.message

    def test_batch_run_in_existing_loop(self, dev_connections):
        flow_folder = "prompt_tools"
        inputs_mapping = {"text": "${data.text}"}
        batch_result = asyncio.run(async_submit_batch_run(flow_folder, inputs_mapping, dev_connections))
        assert isinstance(batch_result, BatchResult)
        assert batch_result.total_lines == batch_result.completed_lines

    def test_batch_run_with_aggregation_failure(self, dev_connections):
        flow_folder = "aggregation_node_failed"
        inputs_mapping = {"groundtruth": "${data.groundtruth}", "prediction": "${data.prediction}"}
        batch_result = submit_batch_run(flow_folder, inputs_mapping, connections=dev_connections)
        assert isinstance(batch_result, BatchResult)
        assert batch_result.total_lines == batch_result.completed_lines
        assert batch_result.node_status == get_flow_expected_status_summary(flow_folder)
        # assert aggregation node error summary
        assert batch_result.failed_lines == 0
        aggre_node_error = batch_result.error_summary.aggr_error_dict["aggregate"]
        assert aggre_node_error["message"] == "Execution failure in 'aggregate': (ZeroDivisionError) division by zero"
        assert aggre_node_error["code"] == "UserError"
        assert aggre_node_error["innerError"] == {"code": "ToolExecutionError", "innerError": None}

    @pytest.mark.parametrize(
        "flow_folder, resume_from_run_name",
        [("web_classification", "web_classification_default_20240207_165606_643000")],
    )
    def test_batch_resume(self, flow_folder, resume_from_run_name, dev_connections):
        run_storage = LocalStorageOperations(Run(flow="web_classification"))
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=run_storage,
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="data.jsonl")}
        output_dir = Path(mkdtemp())
        inputs_mapping = {"url": "${data.url}"}

        run_folder = RUNS_ROOT / resume_from_run_name
        mock_resume_from_run = MockRun(resume_from_run_name, run_folder)
        resume_from_run_storage = LocalStorageOperations(mock_resume_from_run)
        resume_from_run_output_dir = resume_from_run_storage.outputs_folder
        resume_run_id = mock_resume_from_run.name + "_resume"
        resume_run_batch_results = batch_engine.run(
            input_dirs,
            inputs_mapping,
            output_dir,
            resume_run_id,
            resume_from_run_storage=resume_from_run_storage,
            resume_from_run_output_dir=resume_from_run_output_dir,
        )

        nlines = 3
        assert resume_run_batch_results.total_lines == nlines
        assert resume_run_batch_results.completed_lines == nlines

        jsonl_files = glob.glob(os.path.join(run_storage._run_infos_folder, "*.jsonl"))
        for file_path in jsonl_files:
            contents = load_jsonl(file_path)
            for content in contents:
                assert content["run_info"]["root_run_id"] == resume_run_id

    @pytest.mark.parametrize(
        "flow_folder, resume_from_run_name",
        [("classification_accuracy_evaluation", "classification_accuracy_evaluation_default_20240208_152402_694000")],
    )
    def test_batch_resume_aggregation(self, flow_folder, resume_from_run_name, dev_connections):
        run_storage = LocalStorageOperations(Run(flow="classification_accuracy_evaluation"))
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=run_storage,
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="samples.json")}
        output_dir = Path(mkdtemp())
        inputs_mapping = {
            "variant_id": "${data.variant_id}",
            "groundtruth": "${data.groundtruth}",
            "prediction": "${data.prediction}",
        }
        run_folder = RUNS_ROOT / resume_from_run_name
        mock_resume_from_run = MockRun(resume_from_run_name, run_folder)
        resume_from_run_storage = LocalStorageOperations(mock_resume_from_run)
        resume_from_run_output_dir = resume_from_run_storage.outputs_folder
        resume_run_id = mock_resume_from_run.name + "_resume"
        resume_run_batch_results = batch_engine.run(
            input_dirs,
            inputs_mapping,
            output_dir,
            resume_run_id,
            resume_from_run_storage=resume_from_run_storage,
            resume_from_run_output_dir=resume_from_run_output_dir,
        )

        nlines = 3
        assert resume_run_batch_results.total_lines == nlines
        assert resume_run_batch_results.completed_lines == nlines
        assert resume_run_batch_results.metrics == {"accuracy": 0.67}

        jsonl_files = glob.glob(os.path.join(run_storage._run_infos_folder, "*.jsonl"))
        for file_path in jsonl_files:
            contents = load_jsonl(file_path)
            for content in contents:
                assert content["run_info"]["root_run_id"] == resume_run_id

        status_summary = {f"__pf__.nodes.{k}": v for k, v in resume_run_batch_results.node_status.items()}
        assert status_summary["__pf__.nodes.grade.completed"] == 3
        assert status_summary["__pf__.nodes.calculate_accuracy.completed"] == 1
        assert status_summary["__pf__.nodes.aggregation_assert.completed"] == 1

    @pytest.mark.parametrize(
        "flow_folder, resume_from_run_name",
        [("eval_flow_with_image_resume", "eval_flow_with_image_resume_default_20240305_111258_103000")],
    )
    def test_batch_resume_aggregation_with_image(self, flow_folder, resume_from_run_name, dev_connections):
        run_storage = LocalStorageOperations(Run(flow="eval_flow_with_image_resume"))
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=run_storage,
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="data.jsonl")}
        output_dir = Path(mkdtemp())
        inputs_mapping = {"input_image": "${data.input_image}"}
        run_folder = RUNS_ROOT / resume_from_run_name
        mock_resume_from_run = MockRun(resume_from_run_name, run_folder)
        resume_from_run_storage = LocalStorageOperations(mock_resume_from_run)
        resume_from_run_output_dir = resume_from_run_storage.outputs_folder
        resume_run_id = mock_resume_from_run.name + "_resume"
        resume_run_batch_results = batch_engine.run(
            input_dirs,
            inputs_mapping,
            output_dir,
            resume_run_id,
            resume_from_run_storage=resume_from_run_storage,
            resume_from_run_output_dir=resume_from_run_output_dir,
        )

        nlines = 3
        assert resume_run_batch_results.total_lines == nlines
        assert resume_run_batch_results.completed_lines == nlines
        assert resume_run_batch_results.metrics == {"image_count": 3}

        jsonl_files = glob.glob(os.path.join(run_storage._run_infos_folder, "*.jsonl"))
        for file_path in jsonl_files:
            contents = load_jsonl(file_path)
            for content in contents:
                assert content["run_info"]["root_run_id"] == resume_run_id

        status_summary = {f"__pf__.nodes.{k}": v for k, v in resume_run_batch_results.node_status.items()}
        assert status_summary["__pf__.nodes.flip_image.completed"] == 3
        assert status_summary["__pf__.nodes.count_image.completed"] == 1

    @pytest.mark.parametrize(
        "simulation_flow, copilot_flow, max_turn, input_file_name",
        [
            (
                "chat_group/cloud_batch_runs/chat_group_simulation",
                "chat_group/cloud_batch_runs/chat_group_copilot",
                5,
                "inputs.json",
            ),
            (
                "chat_group/cloud_batch_runs/chat_group_simulation",
                "chat_group/cloud_batch_runs/chat_group_copilot",
                5,
                "inputs_using_default_value.json",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_chat_group_batch_run(
        self, simulation_flow, copilot_flow, max_turn, input_file_name, dev_connections
    ):
        simulation_role = ChatRole(
            flow="flow.dag.yaml",  # Use relative path similar with runtime payload
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(simulation_flow),
            connections=dev_connections,
            inputs_mapping={
                "topic": "${data.topic}",
                "ground_truth": "${data.ground_truth}",
                "history": "${parent.conversation_history}",
            },
        )
        copilot_role = ChatRole(
            flow=get_yaml_file(copilot_flow),
            role="assistant",
            name="copilot",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(copilot_flow),
            connections=dev_connections,
            inputs_mapping={"question": "${data.question}", "conversation_history": "${parent.conversation_history}"},
        )
        input_dirs = {"data": get_flow_inputs_file("chat_group/cloud_batch_runs", file_name=input_file_name)}
        output_dir = Path(mkdtemp())
        mem_run_storage = MemoryRunStorage()

        # register python proxy since current python proxy cannot execute single line
        ProxyFactory.register_executor("python", SingleLinePythonExecutorProxy)
        chat_group_orchestrator_proxy = await ChatGroupOrchestratorProxy.create(
            flow_file="", chat_group_roles=[simulation_role, copilot_role], max_turn=max_turn
        )
        batchEngine = BatchEngine(flow_file=None, working_dir=get_flow_folder("chat_group"), storage=mem_run_storage)
        batch_result = batchEngine.run(input_dirs, {}, output_dir, executor_proxy=chat_group_orchestrator_proxy)

        nlines = 3
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == nlines
        assert batch_result.start_time < batch_result.end_time
        assert batch_result.system_metrics.duration > 0

        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        print(outputs)
        assert len(outputs) == nlines
        for i, output in enumerate(outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert "conversation_history" in output, f"conversation_history is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
            # "line_number is the first pair in the dict, conversation_history is the last pair in the dict"
            assert len(output) == max_turn + 2
            conversation_history = output["conversation_history"]
            # generate output value set to dedup output
            # only check user role since assistant role output is generate by LLM, we cannot control the output value
            output_values = {item["output"] for item in conversation_history if item["role"] == "user"}
            assert len(output_values) == 3

        assert len(mem_run_storage._flow_runs) == nlines
        assert all(flow_run_info.status == Status.Completed for flow_run_info in mem_run_storage._flow_runs.values())
        assert all(node_run_info.status == Status.Completed for node_run_info in mem_run_storage._node_runs.values())

        # reset the executor proxy to avoid affecting other tests
        ProxyFactory.register_executor("python", PythonExecutorProxy)

    @pytest.mark.parametrize(
        "simulation_flow, copilot_flow, max_turn, simulation_input_file_name, copilot_input_file_name",
        [
            (
                "chat_group/cloud_batch_runs/chat_group_simulation",
                "chat_group/cloud_batch_runs/chat_group_copilot",
                5,
                "simulation_input.json",
                "copilot_input.json",
            )
        ],
    )
    @pytest.mark.asyncio
    async def test_chat_group_batch_run_multi_inputs(
        self,
        simulation_flow,
        copilot_flow,
        max_turn,
        simulation_input_file_name,
        copilot_input_file_name,
        dev_connections,
    ):
        simulation_role = ChatRole(
            flow=get_yaml_file(simulation_flow),
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(simulation_flow),
            connections=dev_connections,
            inputs_mapping={
                "topic": "${simulation.topic}",
                "ground_truth": "${simulation.ground_truth}",
                "history": "${parent.conversation_history}",
            },
        )
        copilot_role = ChatRole(
            flow=get_yaml_file(copilot_flow),
            role="assistant",
            name="copilot",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(copilot_flow),
            connections=dev_connections,
            inputs_mapping={
                "question": "${copilot.question}",
                "conversation_history": "${parent.conversation_history}",
            },
        )
        input_dirs = {
            "simulation": get_flow_inputs_file("chat_group/cloud_batch_runs", file_name=simulation_input_file_name),
            "copilot": get_flow_inputs_file("chat_group/cloud_batch_runs", file_name=copilot_input_file_name),
        }
        output_dir = Path(mkdtemp())
        mem_run_storage = MemoryRunStorage()

        # register python proxy since current python proxy cannot execute single line
        ProxyFactory.register_executor("python", SingleLinePythonExecutorProxy)
        chat_group_orchestrator_proxy = await ChatGroupOrchestratorProxy.create(
            flow_file="", chat_group_roles=[simulation_role, copilot_role], max_turn=max_turn
        )
        batchEngine = BatchEngine(flow_file=None, working_dir=get_flow_folder("chat_group"), storage=mem_run_storage)
        batch_result = batchEngine.run(input_dirs, {}, output_dir, executor_proxy=chat_group_orchestrator_proxy)

        nlines = 3
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == nlines
        assert batch_result.start_time < batch_result.end_time
        assert batch_result.system_metrics.duration > 0

        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == nlines
        for i, output in enumerate(outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert "conversation_history" in output, f"conversation_history is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
            # "line_number is the first pair in the dict, conversation_history is the last pair in the dict"
            assert len(output) == max_turn + 2
            for j, line in enumerate(output):
                if "line_number" not in output:
                    assert "role" in line, f"role is not in {i}th output {j}th line {line}"

        assert len(mem_run_storage._flow_runs) == nlines
        assert all(flow_run_info.status == Status.Completed for flow_run_info in mem_run_storage._flow_runs.values())
        assert all(node_run_info.status == Status.Completed for node_run_info in mem_run_storage._node_runs.values())

        # reset the executor proxy to avoid affecting other tests
        ProxyFactory.register_executor("python", PythonExecutorProxy)

    @pytest.mark.parametrize(
        "simulation_flow, copilot_flow, max_turn, input_file_name",
        [
            (
                "chat_group/cloud_batch_runs/chat_group_simulation_stop_signal",
                "chat_group/cloud_batch_runs/chat_group_copilot",
                5,
                "inputs.json",
            )
        ],
    )
    @pytest.mark.asyncio
    async def test_chat_group_batch_run_stop_signal(
        self, simulation_flow, copilot_flow, max_turn, input_file_name, dev_connections
    ):
        simulation_role = ChatRole(
            flow=get_yaml_file(simulation_flow),
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(simulation_flow),
            connections=dev_connections,
            inputs_mapping={
                "topic": "${data.topic}",
                "ground_truth": "${data.ground_truth}",
                "history": "${parent.conversation_history}",
            },
        )
        copilot_role = ChatRole(
            flow=get_yaml_file(copilot_flow),
            role="assistant",
            name="copilot",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(copilot_flow),
            connections=dev_connections,
            inputs_mapping={"question": "${data.question}", "conversation_history": "${parent.conversation_history}"},
        )
        input_dirs = {"data": get_flow_inputs_file("chat_group/cloud_batch_runs", file_name=input_file_name)}
        output_dir = Path(mkdtemp())
        mem_run_storage = MemoryRunStorage()

        # register python proxy since current python proxy cannot execute single line
        ProxyFactory.register_executor("python", SingleLinePythonExecutorProxy)
        chat_group_orchestrator_proxy = await ChatGroupOrchestratorProxy.create(
            flow_file="", chat_group_roles=[simulation_role, copilot_role], max_turn=max_turn
        )
        batchEngine = BatchEngine(flow_file=None, working_dir=get_flow_folder("chat_group"), storage=mem_run_storage)
        batch_result = batchEngine.run(input_dirs, {}, output_dir, executor_proxy=chat_group_orchestrator_proxy)

        nlines = 3
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == nlines
        assert batch_result.start_time < batch_result.end_time
        assert batch_result.system_metrics.duration > 0

        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == nlines
        for i, output in enumerate(outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert "conversation_history" in output, f"conversation_history is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
            # hit stop signal. It only has line number conversation history and simulation run output
            assert len(output) == 3
            for j, line in enumerate(output):
                if "line_number" not in output:
                    assert "role" in line, f"role is not in {i}th output {j}th line {line}"

        assert len(mem_run_storage._flow_runs) == nlines
        assert all(flow_run_info.status == Status.Completed for flow_run_info in mem_run_storage._flow_runs.values())
        assert all(node_run_info.status == Status.Completed for node_run_info in mem_run_storage._node_runs.values())

        # reset the executor proxy to avoid affecting other tests
        ProxyFactory.register_executor("python", PythonExecutorProxy)

    @pytest.mark.parametrize(
        "simulation_flow, copilot_flow, max_turn, input_file_name",
        [
            (
                "chat_group/cloud_batch_runs/chat_group_simulation_error",
                "chat_group/cloud_batch_runs/chat_group_copilot",
                5,
                "inputs.json",
            ),
            (
                "chat_group/cloud_batch_runs/chat_group_copilot",
                "chat_group/cloud_batch_runs/chat_group_simulation_error",
                5,
                "inputs.json",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_chat_group_batch_run_early_stop(
        self, simulation_flow, copilot_flow, max_turn, input_file_name, dev_connections
    ):
        simulation_role = ChatRole(
            flow=get_yaml_file(simulation_flow),
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(simulation_flow),
            connections=dev_connections,
            inputs_mapping={
                "topic": "${data.topic}",
                "ground_truth": "${data.ground_truth}",
                "history": "${parent.conversation_history}",
            },
        )
        copilot_role = ChatRole(
            flow=get_yaml_file(copilot_flow),
            role="assistant",
            name="copilot",
            stop_signal="[STOP]",
            working_dir=get_flow_folder(copilot_flow),
            connections=dev_connections,
            inputs_mapping={"question": "${data.question}", "conversation_history": "${parent.conversation_history}"},
        )
        input_dirs = {"data": get_flow_inputs_file("chat_group/cloud_batch_runs", file_name=input_file_name)}
        output_dir = Path(mkdtemp())
        mem_run_storage = MemoryRunStorage()

        # register python proxy since current python proxy cannot execute single line
        ProxyFactory.register_executor("python", SingleLinePythonExecutorProxy)
        chat_group_orchestrator_proxy = await ChatGroupOrchestratorProxy.create(
            flow_file="", chat_group_roles=[simulation_role, copilot_role], max_turn=max_turn
        )
        batchEngine = BatchEngine(flow_file=None, working_dir=get_flow_folder("chat_group"), storage=mem_run_storage)
        batch_result = batchEngine.run(input_dirs, {}, output_dir, executor_proxy=chat_group_orchestrator_proxy)

        nlines = 3
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == 0
        assert batch_result.start_time < batch_result.end_time
        assert batch_result.system_metrics.duration > 0

        # all the line run failed and will not output to file
        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == 0

        # reset the executor proxy to avoid affecting other tests
        ProxyFactory.register_executor("python", PythonExecutorProxy)
