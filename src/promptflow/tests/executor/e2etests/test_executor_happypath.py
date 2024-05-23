import logging
import multiprocessing
import os
import re
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from promptflow.contracts.run_info import Status
from promptflow.exceptions import UserErrorException
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import GetConnectionError, InputTypeError, ResolveToolError
from promptflow.executor.flow_executor import execute_flow
from promptflow.storage._run_storage import DefaultRunStorage

from ..conftest import MockSpawnProcess, setup_recording
from ..process_utils import MockForkServerProcess, override_process_class
from ..utils import FLOW_ROOT, get_flow_folder, get_flow_sample_inputs, get_yaml_file, is_image_file

SAMPLE_FLOW = "web_classification_no_variants"


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections", "recording_injection")
@pytest.mark.e2etest
class TestExecutor:
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

    def skip_serp(self, flow_folder, dev_connections):
        serp_required_flows = ["package_tools"]
        #  Real key is usually more than 32 chars
        serp_key = dev_connections.get("serp_connection", {"value": {"api_key": ""}})["value"]["api_key"]
        if flow_folder in serp_required_flows and len(serp_key) < 32:
            pytest.skip("serp_connection is not prepared")

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
            "prompt_tools",
            "script_with___file__",
            "script_with_import",
            "package_tools",
            "connection_as_input",
            "async_tools",
            "async_tools_with_sync_tools",
            "tool_with_assistant_definition",
        ],
    )
    def test_executor_exec_line(self, flow_folder, dev_connections):
        self.skip_serp(flow_folder, dev_connections)
        os.chdir(get_flow_folder(flow_folder))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(self.get_line_inputs())
        assert not executor._run_tracker._flow_runs, "Flow runs in run tracker should be empty."
        assert not executor._run_tracker._node_runs, "Node runs in run tracker should be empty."
        assert isinstance(flow_result.output, dict)
        assert flow_result.run_info.status == Status.Completed
        node_count = len(executor._flow.nodes)
        assert isinstance(flow_result.run_info.api_calls, list) and len(flow_result.run_info.api_calls) == 1
        assert (
            isinstance(flow_result.run_info.api_calls[0]["children"], list)
            and len(flow_result.run_info.api_calls[0]["children"]) == node_count
        )
        assert len(flow_result.node_run_infos) == node_count
        for node, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert node_run_info.node == node
            assert isinstance(node_run_info.api_calls, list)  # api calls is set

    def test_long_running_log(self, dev_connections, capsys):
        # TODO: investigate why flow_logger does not output to stdout in test case
        from promptflow._utils.logger_utils import flow_logger

        flow_logger.addHandler(logging.StreamHandler(sys.stdout))

        # Test long running tasks with log
        os.environ["PF_LONG_RUNNING_LOGGING_INTERVAL"] = "1"
        executor = FlowExecutor.create(get_yaml_file("async_tools"), dev_connections)
        executor.exec_line(self.get_line_inputs())
        captured = capsys.readouterr()
        expected_long_running_str_1 = r".*.*Task async_passthrough has been running for \d+ seconds, stacktrace:\n.*async_passthrough\.py.*in passthrough_str_and_wait\n.*await asyncio.sleep\(1\).*tasks\.py.*"  # noqa E501
        assert re.match(
            expected_long_running_str_1, captured.out, re.DOTALL
        ), "flow_logger should contain long running async tool log"
        expected_long_running_str_2 = r".*.*Task async_passthrough has been running for \d+ seconds, stacktrace:\n.*async_passthrough\.py.*in passthrough_str_and_wait\n.*await asyncio.sleep\(1\).*tasks\.py.*"  # noqa E501
        assert re.match(
            expected_long_running_str_2, captured.out, re.DOTALL
        ), "flow_logger should contain long running async tool log"
        os.environ.pop("PF_LONG_RUNNING_LOGGING_INTERVAL")

        # Test long running tasks without log
        executor.exec_line(self.get_line_inputs())
        captured = capsys.readouterr()
        assert not re.match(
            expected_long_running_str_1, captured.out, re.DOTALL
        ), "flow_logger should not contain long running async tool log"
        assert not re.match(
            expected_long_running_str_2, captured.out, re.DOTALL
        ), "flow_logger should not contain long running async tool log"

        flow_logger.handlers.pop()

    @pytest.mark.parametrize(
        "flow_folder, node_name, flow_inputs, dependency_nodes_outputs",
        [
            ("web_classification_no_variants", "summarize_text_content", {}, {"fetch_text_content_from_url": "Hello"}),
            ("prompt_tools", "summarize_text_content_prompt", {"text": "text"}, {}),
            ("script_with___file__", "node1", {"text": "text"}, None),
            ("script_with___file__", "node2", None, {"node1": "text"}),
            ("script_with___file__", "node3", None, None),
            ("package_tools", "search_by_text", {"text": "elon mask"}, None),  # Skip since no api key in CI
            ("connection_as_input", "conn_node", None, None),
            ("simple_aggregation", "accuracy", {"text": "A"}, {"passthrough": "B"}),
            ("script_with_import", "node1", {"text": "text"}, None),
        ],
    )
    def test_executor_exec_node(self, flow_folder, node_name, flow_inputs, dependency_nodes_outputs, dev_connections):
        self.skip_serp(flow_folder, dev_connections)
        yaml_file = get_yaml_file(flow_folder)
        run_info = FlowExecutor.load_and_exec_node(
            yaml_file,
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=dev_connections,
            raise_ex=True,
        )
        assert run_info.output is not None
        assert run_info.status == Status.Completed
        assert isinstance(run_info.api_calls, list)
        assert run_info.node == node_name
        assert run_info.system_metrics["duration"] >= 0

    def test_executor_exec_node_with_llm_node(self, dev_connections):
        # Run the test in a new process to ensure the openai api is injected correctly for the single node run
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        process = context.Process(
            target=exec_node_within_process,
            args=(queue, "llm_tool", "joke", {"topic": "fruit"}, {}, dev_connections, True),
        )
        process.start()
        process.join()

        if not queue.empty():
            raise queue.get()

    def test_executor_node_overrides(self, dev_connections):
        inputs = self.get_line_inputs()
        executor = FlowExecutor.create(
            get_yaml_file(SAMPLE_FLOW),
            dev_connections,
            node_override={"classify_with_llm.deployment_name": "dummy_deployment"},
            raise_ex=True,
        )
        with pytest.raises(UserErrorException) as e:
            executor.exec_line(inputs)
        assert type(e.value).__name__ == "WrappedOpenAIError"
        assert "The API deployment for this resource does not exist." in str(e.value)

        with pytest.raises(ResolveToolError) as e:
            executor = FlowExecutor.create(
                get_yaml_file(SAMPLE_FLOW),
                dev_connections,
                node_override={"classify_with_llm.connection": "dummy_connection"},
                raise_ex=True,
            )
        assert isinstance(e.value.inner_exception, GetConnectionError)
        assert (
            "Get connection 'dummy_connection' for node 'classify_with_llm' "
            "error: Connection 'dummy_connection' not found" in str(e.value)
        )

    @pytest.mark.parametrize(
        "flow_folder",
        [
            "no_inputs_outputs",
        ],
    )
    def test_flow_with_no_inputs_and_output(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        flow_result = executor.exec_line({})
        assert flow_result.output == {}
        assert flow_result.run_info.status == Status.Completed
        node_count = len(executor._flow.nodes)
        assert isinstance(flow_result.run_info.api_calls, list) and len(flow_result.run_info.api_calls) == node_count
        assert len(flow_result.node_run_infos) == node_count
        for node, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert node_run_info.node == node
            assert isinstance(node_run_info.api_calls, list)  # api calls is set

    @pytest.mark.parametrize(
        "flow_folder",
        [
            "simple_flow_with_python_tool",
        ],
    )
    def test_convert_flow_input_types(self, flow_folder, dev_connections) -> None:
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        ret = executor.convert_flow_input_types(inputs={"num": "11"})
        assert ret == {"num": 11}
        ret = executor.convert_flow_input_types(inputs={"text": "12", "num": "11"})
        assert ret == {"text": "12", "num": 11}
        with pytest.raises(InputTypeError):
            ret = executor.convert_flow_input_types(inputs={"num": "hello"})
            executor.convert_flow_input_types(inputs={"num": "hello"})

    def test_chat_flow_stream_mode(self, dev_connections) -> None:
        executor = FlowExecutor.create(get_yaml_file("python_stream_tools", FLOW_ROOT), dev_connections)

        # To run a flow with stream output, we need to set this flag to run tracker.
        # TODO: refine the interface

        inputs = {"text": "hello", "chat_history": []}
        line_result = executor.exec_line(inputs, allow_generator_output=True)

        # Assert there's only one output
        assert len(line_result.output) == 1
        assert set(line_result.output.keys()) == {"output_echo"}

        # Assert the only output is a generator
        output_echo = line_result.output["output_echo"]
        assert isinstance(output_echo, Iterator)
        assert list(output_echo) == ["Echo: ", "hello "]

        # Assert the flow is completed and no errors are raised
        flow_run_info = line_result.run_info
        assert flow_run_info.status == Status.Completed
        assert flow_run_info.error is None

    @pytest.mark.parametrize(
        "flow_folder",
        [
            "web_classification",
        ],
    )
    def test_executor_creation_with_default_variants(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(self.get_line_inputs())
        assert flow_result.run_info.status == Status.Completed

    def test_executor_creation_with_default_input(self):
        # Assert for single node run.
        default_input_value = "input value from default"
        yaml_file = get_yaml_file("default_input")
        executor = FlowExecutor.create(yaml_file, {})
        node_result = executor.load_and_exec_node(yaml_file, "test_print_input")
        assert node_result.status == Status.Completed
        assert node_result.output == default_input_value

        # Assert for flow run.
        flow_result = executor.exec_line({})
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.output["output"] == default_input_value
        aggr_results = executor.exec_aggregation({}, aggregation_inputs={})
        flow_aggregate_node = aggr_results.node_run_infos["aggregate_node"]
        assert flow_aggregate_node.status == Status.Completed
        assert flow_aggregate_node.output == [default_input_value]

        # Assert for exec
        exec_result = executor.exec({})
        assert exec_result["output"] == default_input_value

    def test_executor_for_script_tool_with_init(self, dev_connections):
        executor = FlowExecutor.create(get_yaml_file("script_tool_with_init"), dev_connections)
        flow_result = executor.exec_line({"input": "World"})
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.output["output"] == "Hello World"

    @pytest.mark.parametrize(
        "output_dir_name, intermediate_dir_name, run_aggregation, expected_node_counts",
        [
            ("output", "intermediate", True, 2),
            ("output_1", "intermediate_1", False, 1),
        ],
    )
    def test_execute_flow(
        self, output_dir_name: str, intermediate_dir_name: str, run_aggregation: bool, expected_node_counts: int
    ):
        flow_folder = get_flow_folder("eval_flow_with_simple_image")
        # prepare output folder
        output_dir = flow_folder / output_dir_name
        intermediate_dir = flow_folder / intermediate_dir_name
        output_dir.mkdir(exist_ok=True)
        intermediate_dir.mkdir(exist_ok=True)

        storage = DefaultRunStorage(base_dir=flow_folder, sub_dir=Path(intermediate_dir_name))
        line_result = execute_flow(
            flow_file=get_yaml_file(flow_folder),
            working_dir=flow_folder,
            output_dir=Path(output_dir_name),
            inputs={},
            connections={},
            run_aggregation=run_aggregation,
            storage=storage,
        )
        assert line_result.run_info.status == Status.Completed
        assert len(line_result.node_run_infos) == expected_node_counts
        assert all(is_image_file(output_file) for output_file in output_dir.iterdir())
        assert all(is_image_file(output_file) for output_file in intermediate_dir.iterdir())
        # clean up output folder
        shutil.rmtree(output_dir)
        shutil.rmtree(intermediate_dir)


def exec_node_within_process(queue, flow_file, node_name, flow_inputs, dependency_nodes_outputs, connections, raise_ex):
    try:
        process_class_dict = {"spawn": MockSpawnProcess, "forkserver": MockForkServerProcess}
        override_process_class(process_class_dict)

        # recording injection again since this method is running in a new process
        setup_recording()
        result = FlowExecutor.load_and_exec_node(
            flow_file=get_yaml_file(flow_file),
            node_name=node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=connections,
            raise_ex=raise_ex,
        )
        # Assert llm single node run contains openai traces
        # And the traces contains system metrics
        OPENAI_AGGREGATE_METRICS = ["prompt_tokens", "completion_tokens", "total_tokens"]
        assert len(result.api_calls) == 1
        assert len(result.api_calls[0]["children"]) == 1
        assert isinstance(result.api_calls[0]["children"][0]["system_metrics"], dict)
        for key in OPENAI_AGGREGATE_METRICS:
            assert key in result.api_calls[0]["children"][0]["system_metrics"]
        for key in OPENAI_AGGREGATE_METRICS:
            assert (
                result.api_calls[0]["system_metrics"][key] == result.api_calls[0]["children"][0]["system_metrics"][key]
            )
    except Exception as ex:
        queue.put(ex)
