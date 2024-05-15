import asyncio
from dataclasses import is_dataclass
from unittest.mock import patch

import pytest

from promptflow._core.tool_meta_generator import PythonLoadError
from promptflow.contracts.run_info import Status
from promptflow.core import AzureOpenAIModelConfiguration, OpenAIModelConfiguration
from promptflow.core._connection_provider._dict_connection_provider import DictConnectionProvider
from promptflow.executor._errors import (
    FlowEntryInitializationError,
    InputNotFound,
    InputTypeError,
    InvalidFlexFlowEntry,
)
from promptflow.executor._result import LineResult
from promptflow.executor._script_executor import ScriptExecutor
from promptflow.executor.flow_executor import FlowExecutor

from ...conftest import EAGER_FLOW_ROOT, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"


class ClassEntry:
    def __call__(self, input_str: str) -> str:
        return "Hello " + input_str


def func_entry(input_str: str) -> str:
    return "Hello " + input_str


async def func_entry_async(input_str: str) -> str:
    await asyncio.sleep(1)
    return "Hello " + input_str


async def gen_func(input_str: str):
    for i in range(5):
        await asyncio.sleep(0.1)
        yield str(i)


class ClassEntryGen:
    async def __call__(self, input_str: str):
        for i in range(5):
            await asyncio.sleep(0.1)
            yield str(i)


function_entries = [
    (ClassEntry(), {"input_str": "world"}, "Hello world"),
    (func_entry, {"input_str": "world"}, "Hello world"),
    (func_entry_async, {"input_str": "world"}, "Hello world"),
]

generator_entries = [
    (gen_func, {"input_str": "world"}, ["0", "1", "2", "3", "4"]),
    (ClassEntryGen(), {"input_str": "world"}, ["0", "1", "2", "3", "4"]),
]


@pytest.mark.usefixtures("recording_injection", "setup_connection_provider", "dev_connections")
@pytest.mark.e2etest
class TestEagerFlow:
    @pytest.mark.parametrize(
        "flow_folder, inputs, ensure_output, init_kwargs",
        [
            ("dummy_flow_with_trace", {"text": "text", "models": ["model"]}, lambda x: x == "dummy_output", None),
            (
                "flow_with_dataclass_output",
                {"text": "text", "models": ["model"]},
                lambda x: is_dataclass(x) and x.text == "text" and x.models == ["model"],
                None,
            ),
            (
                "basic_callable_class",
                {"func_input": "func_input"},
                lambda x: is_dataclass(x) and x.func_input == "func_input",
                {"obj_input": "obj_input"},
            ),
            (
                "basic_callable_class_async",
                {"func_input": "func_input"},
                lambda x: is_dataclass(x) and x.func_input == "func_input",
                {"obj_input": "obj_input"},
            ),
            (
                "callable_class_with_primitive",
                {"func_input": "func_input"},
                lambda x: x == "The object input is obj_input and the function input is func_input",
                {"obj_input": "obj_input"},
            ),
            (
                "basic_model_config",
                {"func_input": "input"},
                lambda x: x["azure_open_ai_model_config_azure_endpoint"] == "fake_endpoint",
                {
                    "azure_open_ai_model_config": AzureOpenAIModelConfiguration(
                        azure_deployment="my_deployment", azure_endpoint="fake_endpoint"
                    ),
                    "open_ai_model_config": OpenAIModelConfiguration(model="my_model", base_url="fake_base_url"),
                },
            ),
            (
                "basic_model_config",
                {"func_input": "input"},
                lambda x: x["azure_open_ai_model_config_azure_endpoint"] is not None
                and x["open_ai_model_config_connection"] is None,
                {
                    "azure_open_ai_model_config": AzureOpenAIModelConfiguration(
                        azure_deployment="my_deployment", connection="azure_open_ai_connection"
                    ),
                    "open_ai_model_config": OpenAIModelConfiguration(model="my_model", base_url="fake_base_url"),
                },
            ),
            (
                "flow_with_signature",
                {"input_1": "input_1"},
                lambda x: x["output"] == "input_2",
                None,
            ),
            (
                "flow_with_empty_string",
                {"input_1": "test"},
                lambda x: x == "dummy_output",
                None,
            ),
        ],
    )
    def test_flow_run(self, flow_folder, inputs, ensure_output, init_kwargs):
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)

        # Test submitting eager flow to script executor
        executor = ScriptExecutor(flow_file=flow_file, init_kwargs=init_kwargs)
        line_result = executor.exec_line(inputs=inputs, index=0)
        assert isinstance(line_result, LineResult)
        assert ensure_output(line_result.output)

        if executor.has_aggregation_node:
            aggr_result = executor._exec_aggregation(inputs=[line_result.output])
            assert aggr_result.metrics == {"length": 1}

        # Test submitting eager flow to flow executor
        executor = FlowExecutor.create(flow_file=flow_file, connections={}, init_kwargs=init_kwargs)
        line_result1 = executor.exec_line(inputs=inputs, index=0)
        assert isinstance(line_result1, LineResult)
        assert ensure_output(line_result1.output)

        # run the same line again will get same output
        line_result2 = executor.exec_line(inputs=inputs, index=0)
        assert line_result1.output == line_result2.output

    def test_flow_run_with_openai_chat(self):
        flow_file = get_yaml_file("callable_class_with_openai", root=EAGER_FLOW_ROOT, file_name="flow.flex.yaml")

        # Case 1: Normal case
        executor = ScriptExecutor(flow_file=flow_file, init_kwargs={"connection": "azure_open_ai_connection"})
        line_result = executor.exec_line(inputs={"question": "Hello", "stream": False}, index=0)
        assert line_result.run_info.status == Status.Completed, line_result.run_info.error
        token_names = ["prompt_tokens", "completion_tokens", "total_tokens"]
        for token_name in token_names:
            assert token_name in line_result.run_info.api_calls[0]["children"][0]["system_metrics"]
            assert line_result.run_info.api_calls[0]["children"][0]["system_metrics"][token_name] > 0

        # Case 2: OpenAi metrics calculation failure will not raise error
        with patch(
            "promptflow.tracing._openai_utils.OpenAIMetricsCalculator._try_get_model", return_value="invalid_model"
        ):
            executor = ScriptExecutor(flow_file=flow_file, init_kwargs={"connection": "azure_open_ai_connection"})
            line_result = executor.exec_line(inputs={"question": "Hello", "stream": True}, index=0)
            assert line_result.run_info.status == Status.Completed, line_result.run_info.error
            token_names = ["prompt_tokens", "completion_tokens", "total_tokens"]
            for token_name in token_names:
                assert token_name not in line_result.run_info.api_calls[0]["children"][0]["system_metrics"]

    def test_flow_run_with_connection(self, dev_connections):
        flow_file = get_yaml_file(
            "dummy_callable_class_with_connection", root=EAGER_FLOW_ROOT, file_name="flow.flex.yaml"
        )

        # Test submitting eager flow to script executor with connection dictionary
        executor = ScriptExecutor(
            flow_file=flow_file, connections=dev_connections, init_kwargs={"connection": "azure_open_ai_connection"}
        )
        line_result = executor.exec_line(inputs={}, index=0)
        assert line_result.run_info.status == Status.Completed, line_result.run_info.error

        # Test submitting eager flow to script executor with connection provider
        executor = ScriptExecutor(
            flow_file=flow_file,
            connections=DictConnectionProvider(dev_connections),
            init_kwargs={"connection": "azure_open_ai_connection"},
        )
        line_result = executor.exec_line(inputs={}, index=0)
        assert line_result.run_info.status == Status.Completed, line_result.run_info.error

    @pytest.mark.parametrize("entry, inputs, expected_output", function_entries)
    def test_flow_run_with_function_entry(self, entry, inputs, expected_output):
        executor = FlowExecutor.create(entry, {})
        line_result = executor.exec_line(inputs=inputs)
        assert line_result.run_info.status == Status.Completed
        assert line_result.output == expected_output

    @pytest.mark.asyncio
    @pytest.mark.parametrize("entry, inputs, expected_output", function_entries)
    async def test_flow_run_with_function_entry_async(self, entry, inputs, expected_output):
        executor = FlowExecutor.create(entry, {})
        task1 = asyncio.create_task(executor.exec_line_async(inputs=inputs))
        task2 = asyncio.create_task(executor.exec_line_async(inputs=inputs))
        line_result1, line_result2 = await asyncio.gather(task1, task2)
        for line_result in [line_result1, line_result2]:
            assert line_result.run_info.status == Status.Completed
            assert line_result.output == expected_output
        delta_sec = (line_result2.run_info.end_time - line_result1.run_info.end_time).total_seconds()
        delta_desc = f"{delta_sec}s from {line_result1.run_info.end_time} to {line_result2.run_info.end_time}"
        msg = f"The two tasks should run concurrently, but got {delta_desc}"
        assert 0 <= delta_sec < 0.1, msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("entry, inputs, expected_output", generator_entries)
    async def test_flow_run_with_generator_entry(self, entry, inputs, expected_output):
        executor = FlowExecutor.create(entry, {})

        line_result = executor.exec_line(inputs=inputs)
        assert line_result.run_info.status == Status.Completed
        assert line_result.output == "".join(expected_output)  # When stream=False, it should be a string

        line_result = await executor.exec_line_async(inputs=inputs)
        assert line_result.run_info.status == Status.Completed
        assert line_result.output == "".join(expected_output)  # When stream=False, it should be a string

        line_result = await executor.exec_line_async(inputs=inputs, allow_generator_output=True)
        assert line_result.run_info.status == Status.Completed
        list_result = []
        async for item in line_result.output:
            list_result.append(item)
        assert list_result == expected_output  # When stream=True, it should be an async generator

    def test_flow_run_with_invalid_inputs(self):
        # Case 1: input not found
        flow_file = get_yaml_file("flow_with_signature", root=EAGER_FLOW_ROOT)
        executor = FlowExecutor.create(flow_file=flow_file, connections={}, init_kwargs=None)
        with pytest.raises(InputNotFound) as e:
            executor.exec_line(inputs={}, index=0)
        assert "The input for flow is incorrect." in str(e.value)

        # Case 2: input type mismatch
        flow_file = get_yaml_file("flow_with_wrong_type", root=EAGER_FLOW_ROOT)
        executor = FlowExecutor.create(flow_file=flow_file, connections={}, init_kwargs=None)
        with pytest.raises(InputTypeError) as e:
            executor.exec_line(inputs={"input_1": 1}, index=0)
        assert "does not match the expected type" in str(e.value)

    def test_flow_run_with_invalid_case(self):
        flow_folder = "dummy_flow_with_exception"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        executor = ScriptExecutor(flow_file=flow_file)
        line_result = executor.exec_line(inputs={"text": "text"}, index=0)

        assert isinstance(line_result, LineResult)
        assert line_result.output is None
        assert line_result.run_info.status == Status.Failed
        assert "dummy exception" in line_result.run_info.error["message"]

    def test_flow_with_operation_context(self):
        flow_folder = "flow_with_operation_context"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        executor = FlowExecutor.create(flow_file=flow_file, connections={})
        line_result = executor.exec_line(inputs={}, index=0)

        assert isinstance(line_result, LineResult)
        assert line_result.run_info.status == Status.Completed
        assert line_result.output["flow-id"] == line_result.run_info.flow_id
        assert line_result.output["root-run-id"] == line_result.run_info.root_run_id

    def test_execute_init_func_with_user_error(self):
        flow_folder = "callable_flow_with_init_exception"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        with pytest.raises(FlowEntryInitializationError) as e:
            ScriptExecutor(flow_file=flow_file, init_kwargs={})
        assert "Failed to initialize flow entry with" in str(e.value)

    @pytest.mark.parametrize(
        "flow_folder, expected_exception, expected_error_msg",
        [
            ("callable_flow_with_init_exception", FlowEntryInitializationError, "Failed to initialize flow entry with"),
            ("invalid_illegal_entry", PythonLoadError, "Failed to load python module for"),
            ("incorrect_entry", InvalidFlexFlowEntry, "Invalid entry"),
        ],
    )
    def test_execute_func_with_user_error(self, flow_folder, expected_exception, expected_error_msg):
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        with pytest.raises(expected_exception) as e:
            ScriptExecutor(flow_file=flow_file)
        assert expected_error_msg in str(e.value)

    def test_aggregation_error(self):
        flow_folder = "class_based_flow_with_aggregation_exception"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        executor = ScriptExecutor(flow_file=flow_file, init_kwargs={"obj_input": "obj_input"})
        line_result = executor.exec_line(inputs={"func_input": "func_input"}, index=0)

        if executor.has_aggregation_node:
            aggr_result = executor._exec_aggregation(inputs=[line_result.output])
            # exec aggregation won't fail with error
            assert aggr_result.metrics == {}

    def test_get_function_name(self):
        expected_names = ["ClassEntry.__call__", "func_entry", "func_entry_async"]
        for (entry, _, _), expected_name in zip(function_entries, expected_names):
            executor = FlowExecutor.create(entry, {})
            assert executor._func_name == expected_name

    @pytest.mark.parametrize(
        "flow_folder, expected_output",
        [
            (
                "flow_with_sample",
                {
                    "func_input1": "val1",
                    "func_input2": "val2",
                    "line_number": 0,
                    "obj_input1": "val1",
                    "obj_input2": "val2",
                },
            ),
            ("function_flow_with_sample", {"func_input1": "val1", "func_input2": "val2", "line_number": 0}),
        ],
    )
    def test_flow_with_sample(self, flow_folder, expected_output):
        # when inputs & init not provided, will use sample field in flow file
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        executor = FlowExecutor.create(flow_file=flow_file, connections={})
        line_result = executor.exec_line(inputs={}, index=0)
        assert line_result.run_info.error is None
        assert line_result.output == expected_output
