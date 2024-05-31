import json
import multiprocessing
import sys
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import opentelemetry.trace as otel_trace
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace.status import StatusCode

from promptflow._utils.tool_utils import get_inputs_for_prompt_template
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.executor._result import LineResult
from promptflow.tracing import trace
from promptflow.tracing._utils import serialize
from promptflow.tracing.contracts.trace import TraceType

from ..process_utils import execute_function_in_subprocess, override_process_pool_targets
from ..utils import (
    MemoryRunStorage,
    get_flow_folder,
    get_flow_sample_inputs,
    get_yaml_file,
    load_content,
    prepare_memory_exporter,
    submit_batch_run,
)

LLM_FUNCTION_NAMES = [
    "openai.resources.chat.completions.Completions.create",
    "openai.resources.completions.Completions.create",
    "openai.resources.chat.completions.AsyncCompletions.create",
    "openai.resources.completions.AsyncCompletions.create",
]

EMBEDDING_FUNCTION_NAMES = [
    "openai.resources.embeddings.Embeddings.create",
    "openai.resources.embeddings.AsyncEmbeddings.create",
]

LLM_TOKEN_NAMES = [
    "llm.usage.prompt_tokens",
    "llm.usage.completion_tokens",
    "llm.usage.total_tokens",
    "llm.response.model",
]

EMBEDDING_TOKEN_NAMES = [
    "llm.usage.prompt_tokens",
    "llm.usage.total_tokens",
    "llm.response.model",
]

CUMULATIVE_LLM_TOKEN_NAMES = [
    "__computed__.cumulative_token_count.prompt",
    "__computed__.cumulative_token_count.completion",
    "__computed__.cumulative_token_count.total",
]

CUMULATIVE_EMBEDDING_TOKEN_NAMES = [
    "__computed__.cumulative_token_count.prompt",
    "__computed__.cumulative_token_count.total",
]

SHOULD_INCLUDE_PROMPT_FUNCTION_NAMES = [
    "render_template_jinja2",
    "AzureOpenAI.chat",
]

lock = multiprocessing.Lock()


class JsonSpanExporter(SpanExporter):
    _lock = threading.Lock()

    def __init__(self, file_path):
        self.file_path = file_path

    def export(self, spans):
        try:
            if self._lock:
                with open(self.file_path, "a") as f:
                    for span in spans:
                        f.write(span.to_json() + "\n\n")
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self):
        pass


def mock_exporter_for_batch_tracing():
    patch_targets = {
        "promptflow.executor.flow_executor.setup_exporter_from_environ": mock_setup_exporter_from_environ,
    }
    for target, func in patch_targets.items():
        patcher = patch(target, func)
        patcher.start()


def mock_setup_exporter_from_environ():
    with lock:
        idx = len(list(Path("./.span").glob("*.jsonl")))
        Path(f"./.span/line_span_{idx}.jsonl").touch()
    tracer_provider = TracerProvider()
    json_exporter = JsonSpanExporter(file_path=f"./.span/line_span_{idx}.jsonl")
    tracer_provider.add_span_processor(SimpleSpanProcessor(json_exporter))
    otel_trace.set_tracer_provider(tracer_provider)


def mock_process_wrapper(*args, **kwargs):
    mock_exporter_for_batch_tracing()
    _process_wrapper(*args, **kwargs)


def mock_process_manager(*args, **kwargs):
    mock_exporter_for_batch_tracing()
    create_spawned_fork_process_manager(*args, **kwargs)


def get_chat_input(stream):
    return {
        "question": "What is the capital of the United States of America?",
        "chat_history": [],
        "stream": stream,
    }


def get_completion_input(stream):
    return {"prompt": "What is the capital of the United States of America?", "stream": stream}


@trace
def top_level_function():
    return sub_level_function()


@trace
def sub_level_function():
    return "Hello, World!"


@pytest.mark.usefixtures("dev_connections", "recording_injection")
@pytest.mark.e2etest
class TestExecutorTraces:
    def validate_openai_apicall(self, apicall: dict):
        """Validates an apicall dict.

        Ensure that the trace output of openai api is a list of dicts.

        Args:
            apicall (dict): A dictionary representing apicall.

        Raises:
            AssertionError: If the API call is invalid.
        """
        get_trace = False
        if apicall.get("name", "") in (
            "openai_completion_legacy",
            "openai_chat_legacy",
            "openai_embedding_legacy",
            "openai_chat",  # openai>=1.0.0
            "openai_completion",  # openai>=1.0.0
        ):
            get_trace = True
            output = apicall.get("output")
            assert not isinstance(output, str)
            assert isinstance(output, (list, dict))
            if isinstance(output, list):
                assert all(isinstance(item, dict) for item in output)

        children = apicall.get("children", [])

        if children is not None:
            for child in children:
                get_trace = get_trace or self.validate_openai_apicall(child)

        return get_trace

    @pytest.mark.parametrize(
        "flow_folder, inputs",
        [
            ("openai_chat_api_flow", get_chat_input(False)),
            ("openai_chat_api_flow", get_chat_input(True)),
            ("openai_completion_api_flow", get_completion_input(False)),
            ("openai_completion_api_flow", get_completion_input(True)),
            ("llm_tool", {"topic": "Hello", "stream": False}),
            ("llm_tool", {"topic": "Hello", "stream": True}),
        ],
    )
    def test_executor_openai_api_flow(self, flow_folder, inputs, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(inputs)

        assert isinstance(flow_result.output, dict)
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.run_info.api_calls is not None

        for token_name in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            assert token_name in flow_result.run_info.system_metrics
            assert flow_result.run_info.system_metrics[token_name] > 0

        get_traced = False
        for api_call in flow_result.run_info.api_calls:
            get_traced = get_traced or self.validate_openai_apicall(serialize(api_call))

        assert get_traced is True

    def test_executor_generator_tools(self, dev_connections):
        executor = FlowExecutor.create(get_yaml_file("generator_tools"), dev_connections)
        inputs = {"text": "This is a test"}
        flow_result = executor.exec_line(inputs)

        assert isinstance(flow_result.output, dict)
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.run_info.api_calls is not None

        tool_trace = flow_result.run_info.api_calls[0]["children"][0]
        generator_trace = tool_trace.get("children")[0]
        assert generator_trace is not None

        output = generator_trace.get("output")
        assert isinstance(output, list)

    @pytest.mark.parametrize("allow_generator_output", [False, True])
    def test_trace_behavior_with_generator_node(self, dev_connections, allow_generator_output):
        """Test to verify the trace output list behavior for a flow with a generator node.

        This test checks the trace output list in two scenarios based on the 'allow_generator_output' flag:
        - When 'allow_generator_output' is True, the output list should initially be empty until the generator is
        consumed.
        - When 'allow_generator_output' is False, the output list should contain items produced by the generator node.

        The test ensures that the trace accurately reflects the generator's consumption status and helps in monitoring
        and debugging flow execution.
        """
        # Set up executor with a flow that contains a generator node
        executor = FlowExecutor.create(get_yaml_file("generator_nodes"), dev_connections)
        inputs = {"text": "This is a test"}

        # Execute the flow with the given inputs and 'allow_generator_output' setting
        flow_result = executor.exec_line(inputs, allow_generator_output=allow_generator_output)

        # Verify that the flow execution result is a dictionary and the flow has completed successfully
        assert isinstance(flow_result.output, dict)
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.run_info.api_calls is not None

        # Extract the trace for the generator node
        tool_trace = flow_result.run_info.api_calls[0]["children"][0]
        generator_output_trace = tool_trace.get("output")

        # Verify that the trace output is a list
        assert isinstance(generator_output_trace, list)
        if allow_generator_output:
            # If generator output is allowed, the trace list should be empty before consumption
            assert not generator_output_trace
            # Obtain the generator from the flow result
            answer_gen = flow_result.output.get("answer")
            assert isinstance(answer_gen, Iterator)
            # Consume the generator and check that it yields text
            try:
                generated_text = next(answer_gen)
                assert isinstance(generated_text, str)
                # Verify the trace list contains the most recently generated item
                assert generator_output_trace[-1] == generated_text
            except StopIteration:
                assert False, "Generator did not generate any text"
        else:
            # If generator output is not allowed, the trace list should contain generated items
            assert generator_output_trace
            assert all(isinstance(item, str) for item in generator_output_trace)

    @pytest.mark.parametrize("flow_file", ["flow_with_trace", "flow_with_trace_async"])
    def test_flow_with_trace(self, flow_file, dev_connections):
        """Tests to verify the flows that contains @trace marks.

        They should generate traces with "Function" type and nested in the "Tool" traces.

        This test case is to verify a flow like following structure, both sync and async mode:

        .. code-block::
            flow (Flow, 1.5s)
                greetings (Tool, 1.5s)
                    get_user_name (Function, 1.0s)
                        is_valid_name (Function, 0.5s)
                    format_greeting (Function, 0.5s)

        """
        executor = FlowExecutor.create(get_yaml_file(flow_file), dev_connections)
        inputs = {"user_id": 1}
        flow_result = executor.exec_line(inputs)

        # Assert the run status is completed
        assert flow_result.output == {"output": "Hello, User 1!"}
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.run_info.api_calls is not None

        # Verify the traces are as expected
        api_calls = flow_result.run_info.api_calls
        assert len(api_calls) == 1

        # Assert the "flow" root level trace
        flow_trace = api_calls[0]
        assert flow_trace["name"] == "flow"
        assert flow_trace["type"] == "Flow"
        assert len(flow_trace["children"]) == 1
        assert flow_trace["system_metrics"]["prompt_tokens"] == 0
        assert flow_trace["system_metrics"]["completion_tokens"] == 0
        assert flow_trace["system_metrics"]["total_tokens"] == 0
        assert isinstance(flow_trace["inputs"], dict)
        assert flow_trace["output"] == {"output": "Hello, User 1!"}
        assert flow_trace["error"] is None
        if sys.platform != "darwin":
            assert flow_trace["end_time"] - flow_trace["start_time"] == pytest.approx(1.5, abs=0.3)
            assert flow_trace["system_metrics"]["duration"] == pytest.approx(1.5, abs=0.3)

        # Assert the "greetings" tool
        greetings_trace = flow_trace["children"][0]
        assert greetings_trace["name"] == "greetings"
        assert greetings_trace["type"] == "Function"
        assert greetings_trace["inputs"] == inputs
        assert greetings_trace["output"] == {"greeting": "Hello, User 1!"}
        assert greetings_trace["error"] is None
        assert greetings_trace["children"] is not None
        assert len(greetings_trace["children"]) == 2
        # TODO: to verfiy the system metrics. This might need to be fixed.
        assert greetings_trace["system_metrics"] == {}
        # This test runs for a longer time on MacOS, so we skip the time assertion on Mac.
        if sys.platform != "darwin":
            assert greetings_trace["end_time"] - greetings_trace["start_time"] == pytest.approx(1.5, abs=0.3)

        # Assert the "get_user_name" function
        get_user_name_trace = greetings_trace["children"][0]
        assert get_user_name_trace["name"] == "get_user_name"
        assert get_user_name_trace["type"] == "Function"
        assert get_user_name_trace["inputs"] == {"user_id": 1}
        assert get_user_name_trace["output"] == "User 1"
        assert get_user_name_trace["error"] is None
        assert len(get_user_name_trace["children"]) == 1
        # TODO: to verfiy the system metrics. This might need to be fixed.
        assert get_user_name_trace["system_metrics"] == {}
        # This test runs for a longer time on MacOS, so we skip the time assertion on Mac.
        if sys.platform != "darwin":
            assert get_user_name_trace["end_time"] - get_user_name_trace["start_time"] == pytest.approx(1.0, abs=0.2)

        # Assert the "get_user_name/is_valid_name" function
        is_valid_name_trace = get_user_name_trace["children"][0]
        assert is_valid_name_trace["name"] == "is_valid_name"
        assert is_valid_name_trace["type"] == "Function"
        assert is_valid_name_trace["inputs"] == {"name": "User 1"}
        assert is_valid_name_trace["output"] is True
        assert is_valid_name_trace["error"] is None
        assert is_valid_name_trace["children"] == []
        # TODO: to verfiy the system metrics. This might need to be fixed.
        assert is_valid_name_trace["system_metrics"] == {}
        # This test runs for a longer time on MacOS, so we skip the time assertion on Mac.
        if sys.platform != "darwin":
            assert is_valid_name_trace["end_time"] - is_valid_name_trace["start_time"] == pytest.approx(0.5, abs=0.1)

        # Assert the "format_greeting" function
        format_greeting_trace = greetings_trace["children"][1]
        assert format_greeting_trace["name"] == "format_greeting"
        assert format_greeting_trace["type"] == "Function"
        assert format_greeting_trace["inputs"] == {"user_name": "User 1"}
        assert format_greeting_trace["output"] == "Hello, User 1!"
        assert format_greeting_trace["error"] is None
        assert format_greeting_trace["children"] == []
        # TODO: to verfiy the system metrics. This might need to be fixed.
        assert format_greeting_trace["system_metrics"] == {}
        # This test runs for a longer time on MacOS, so we skip the time assertion on Mac..
        if sys.platform != "darwin":
            assert format_greeting_trace["end_time"] - format_greeting_trace["start_time"] == pytest.approx(
                0.5, abs=0.1
            )


@pytest.mark.usefixtures("dev_connections", "recording_injection")
@pytest.mark.e2etest
class TestOTelTracer:
    @pytest.mark.parametrize(
        "flow_file, inputs, expected_span_length",
        [
            ("flow_with_trace", {"user_id": 1}, 5),
            ("flow_with_trace_async", {"user_id": 1}, 5),
        ],
    )
    def test_otel_trace(
        self,
        dev_connections,
        flow_file,
        inputs,
        expected_span_length,
    ):
        execute_function_in_subprocess(
            self.assert_otel_traces, dev_connections, flow_file, inputs, expected_span_length
        )

    def assert_otel_traces(self, dev_connections, flow_file, inputs, expected_span_length):
        memory_exporter = prepare_memory_exporter()

        line_result, line_run_id = self.submit_flow_run(flow_file, inputs, dev_connections)
        assert isinstance(line_result, LineResult)
        assert isinstance(line_result.output, dict)

        span_list = memory_exporter.get_finished_spans()
        self.validate_span_list(span_list, line_run_id, expected_span_length)

    @pytest.mark.parametrize(
        "flow_file, inputs, prompt_tpl_file",
        [
            ("llm_tool", {"topic": "Hello", "stream": False}, "joke.jinja2"),
            # Add back this test case after changing the interface of render_template_jinja2
            # ("prompt_tools", {"text": "test"}, "summarize_text_content_prompt.jinja2"),
        ],
    )
    def test_otel_trace_with_prompt(
        self,
        dev_connections,
        flow_file,
        inputs,
        prompt_tpl_file,
    ):
        execute_function_in_subprocess(
            self.assert_otel_traces_with_prompt,
            dev_connections,
            flow_file,
            inputs,
            prompt_tpl_file,
        )

    def assert_otel_traces_with_prompt(self, dev_connections, flow_file, inputs, prompt_tpl_file):
        memory_exporter = prepare_memory_exporter()

        line_result, _ = self.submit_flow_run(flow_file, inputs, dev_connections)
        assert isinstance(line_result, LineResult)
        assert isinstance(line_result.output, dict)

        prompt_tpl = load_content(get_flow_folder(flow_file) / prompt_tpl_file)
        prompt_vars = list(get_inputs_for_prompt_template(prompt_tpl).keys())
        span_list = memory_exporter.get_finished_spans()
        for span in span_list:
            assert span.status.status_code == StatusCode.OK
            assert isinstance(span.name, str)
            if span.attributes.get("function", "") in SHOULD_INCLUDE_PROMPT_FUNCTION_NAMES:
                assert "prompt.template" in span.attributes
                assert span.attributes["prompt.template"] == prompt_tpl
                assert "prompt.variables" in span.attributes
                for var in prompt_vars:
                    if var in inputs:
                        assert var in span.attributes["prompt.variables"]

    @pytest.mark.parametrize(
        "flow_file, inputs, is_stream, expected_span_length",
        [
            ("openai_chat_api_flow", get_chat_input(False), False, 3),
            ("openai_chat_api_flow", get_chat_input(True), True, 3),
            ("openai_completion_api_flow", get_completion_input(False), False, 3),
            ("openai_completion_api_flow", get_completion_input(True), True, 3),
            ("llm_tool", {"topic": "Hello", "stream": False}, False, 4),
            ("flow_with_async_llm_tasks", get_flow_sample_inputs("flow_with_async_llm_tasks"), False, 6),
        ],
    )
    def test_otel_trace_with_llm(
        self,
        dev_connections,
        flow_file,
        inputs,
        is_stream,
        expected_span_length,
    ):
        execute_function_in_subprocess(
            self.assert_otel_traces_with_llm,
            dev_connections,
            flow_file,
            inputs,
            is_stream,
            expected_span_length,
        )

    def assert_otel_traces_with_llm(self, dev_connections, flow_file, inputs, is_stream, expected_span_length):
        memory_exporter = prepare_memory_exporter()

        line_result, line_run_id = self.submit_flow_run(flow_file, inputs, dev_connections)
        assert isinstance(line_result, LineResult)
        assert isinstance(line_result.output, dict)

        span_list = memory_exporter.get_finished_spans()
        self.validate_span_list(span_list, line_run_id, expected_span_length)
        # We updated the OpenAI tokens (prompt_token/completion_token/total_token) to the span attributes
        # for llm and embedding traces, and aggregate them to the parent span. Use this function to validate
        # the openai tokens are correctly set.
        self.validate_openai_tokens(span_list, is_stream)

    @pytest.mark.parametrize(
        "flow_file, inputs, expected_span_length",
        [
            ("openai_embedding_api_flow", {"input": "Hello"}, 3),
            # [9906] is the tokenized version of "Hello"
            ("openai_embedding_api_flow_with_token", {"input": [9906]}, 3),
        ],
    )
    def test_otel_trace_with_embedding(
        self,
        dev_connections,
        flow_file,
        inputs,
        expected_span_length,
    ):
        execute_function_in_subprocess(
            self.assert_otel_traces_with_embedding,
            dev_connections,
            flow_file,
            inputs,
            expected_span_length,
        )

    def assert_otel_traces_with_embedding(self, dev_connections, flow_file, inputs, expected_span_length):
        memory_exporter = prepare_memory_exporter()

        line_result, line_run_id = self.submit_flow_run(flow_file, inputs, dev_connections)
        assert isinstance(line_result, LineResult)
        assert isinstance(line_result.output, dict)

        span_list = memory_exporter.get_finished_spans()
        self.validate_span_list(span_list, line_run_id, expected_span_length)
        for span in span_list:
            if span.attributes.get("function", "") in EMBEDDING_FUNCTION_NAMES:
                assert "ada" in span.attributes.get("llm.response.model", "")
                embeddings = span.attributes.get("embedding.embeddings", "")
                assert "embedding.vector" in embeddings
                assert "embedding.text" in embeddings
                if isinstance(inputs["input"], list):
                    # If the input is a token array, which is list of int, the attribute should contains
                    # the length of the token array '<len(token_array) dimensional token>'.
                    assert "dimensional token" in embeddings
                else:
                    # If the input is a string, the attribute should contains the original input string.
                    assert inputs["input"] in embeddings

    def test_flow_with_traced_function(self):
        execute_function_in_subprocess(self.assert_otel_traces_run_flow_then_traced_function)

    def assert_otel_traces_run_flow_then_traced_function(self):
        memory_exporter = prepare_memory_exporter()

        line_result, _ = self.submit_flow_run("flow_with_trace", {"user_id": 1}, {})
        assert line_result.output == {"output": "Hello, User 1!"}

        top_level_function()  # Call a traced function and check the span list

        span_list = memory_exporter.get_finished_spans()
        assert len(span_list) == 7, f"Got {len(span_list)} spans."  # 4 + 1 + 2 spans in total
        root_spans = [span for span in span_list if span.parent is None]
        assert len(root_spans) == 2, f"Expected 2 root spans, got {len(root_spans)}"
        assert root_spans[0].attributes["span_type"] == TraceType.FLOW  # The flow span
        top_level_span = root_spans[1]
        assert top_level_span.attributes["function"] == "top_level_function"
        assert top_level_span == span_list[-1]  # It should be the last span
        sub_level_span = span_list[-2]  # It should be the second last span
        expected_values = {
            "framework": "promptflow",
            "span_type": "Function",
            "inputs": "{}",
            "output": '"Hello, World!"',
        }
        for span in [top_level_span, sub_level_span]:
            for k, v in expected_values.items():
                assert span.attributes[k] == v, f"span.attributes[{k}] = {span.attributes[k]}, expected: {v}"
            assert "line_run_id" not in span.attributes  # The traced function is not part of the flow
        assert (
            sub_level_span.parent.span_id == top_level_span.context.span_id
        )  # sub_level_span is a child of top_level_span

    def test_flow_with_nested_tool(self):
        memory_exporter = prepare_memory_exporter()

        line_result, _ = self.submit_flow_run("flow_with_nested_tool", {"input": "Hello"}, {})
        assert line_result.output == {"output": "Hello"}

        span_list = memory_exporter.get_finished_spans()
        for span in span_list:
            if span.attributes.get("span_type", "") != "Flow":
                inputs = span.attributes.get("inputs", None)
                if '"recursive_call": false' in inputs:
                    assert span.name == "nested_tool"
                else:
                    assert span.name == "nested_tool_node"

    def test_otel_trace_with_batch(self, dev_connections):
        flow_file = "flow_with_trace"
        execute_function_in_subprocess(self.assert_otel_traces_with_batch, dev_connections, flow_file)

    def assert_otel_traces_with_batch(self, dev_connections, flow_file):
        flow_folder = get_flow_folder(flow_file)
        if (span_folder := flow_folder / ".span").exists():
            for file in span_folder.glob("*.jsonl"):
                file.unlink()
        else:
            span_folder.mkdir()

        with override_process_pool_targets(process_manager=mock_process_manager, process_wrapper=mock_process_wrapper):
            mem_run_storage = MemoryRunStorage()
            batch_result = submit_batch_run(
                flow_folder=flow_file,
                inputs_mapping={"user_id": "${data.user_id}"},
                input_file_name="inputs.jsonl",
                connections=dev_connections,
                storage=mem_run_storage,
            )
            assert isinstance(batch_result, BatchResult)

            batch_run_id = list(mem_run_storage._flow_runs.values())[0].root_run_id
            assert (flow_folder / ".span").exists()
            trace_ids = []
            for file in span_folder.glob("*.jsonl"):
                spans = []
                with open(file, "r") as f:
                    json_chunks = f.read().strip().split("\n\n")
                    for chunk in json_chunks:
                        spans.append(json.loads(chunk))
                trace_ids.append(spans[0]["context"]["trace_id"])
                assert len(spans) == 5, f"Got {len(spans)} spans."
                root_spans = [span for span in spans if span["parent_id"] is None]
                assert len(root_spans) == 1
                root_span = root_spans[0]
                for span in spans:
                    span["status"]["status_code"] = "OK"
                    span["attributes"]["batch_run_id"] = batch_run_id
                    span["attributes"]["framework"] = "promptflow"
                    if span["parent_id"] is None:
                        expected_span_type = "Flow"
                    elif span["attributes"].get("function", "") in LLM_FUNCTION_NAMES:
                        expected_span_type = "LLM"
                    elif span["attributes"].get("function", "") in EMBEDDING_FUNCTION_NAMES:
                        expected_span_type = "Embedding"
                    else:
                        expected_span_type = "Function"
                    msg = f"span_type: {span['attributes']['span_type']}, expected: {expected_span_type}"
                    assert span["attributes"]["span_type"] == expected_span_type, msg
                    if span != root_span:  # Non-root spans should have a parent
                        assert span["attributes"]["function"]
                    inputs = json.loads(span["attributes"]["inputs"])
                    output = json.loads(span["attributes"]["output"])
                    assert isinstance(inputs, dict)
                    assert output is not None

            for run_info in mem_run_storage._flow_runs.values():
                assert f"0x{int(run_info.otel_trace_id, 16):032x}" in trace_ids

    def submit_flow_run(self, flow_file, inputs, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_file), dev_connections)
        line_run_id = str(uuid.uuid4())
        line_result = executor.exec_line(inputs, run_id=line_run_id)
        return line_result, line_run_id

    def validate_span_list(self, span_list, line_run_id, expected_span_length):
        assert len(span_list) == expected_span_length, f"Got {len(span_list)} spans."
        root_spans = [span for span in span_list if span.parent is None]
        assert len(root_spans) == 1
        root_span = root_spans[0]
        for span in span_list:
            assert span.status.status_code == StatusCode.OK
            assert isinstance(span.name, str)
            assert span.attributes["line_run_id"] == line_run_id
            assert span.attributes["framework"] == "promptflow"
            if span.parent is None:
                expected_span_type = TraceType.FLOW
            elif span.attributes.get("function", "") in LLM_FUNCTION_NAMES:
                expected_span_type = TraceType.LLM
            elif span.attributes.get("function", "") in EMBEDDING_FUNCTION_NAMES:
                expected_span_type = TraceType.EMBEDDING
            else:
                expected_span_type = TraceType.FUNCTION
            msg = f"span_type: {span.attributes['span_type']}, expected: {expected_span_type}"
            assert span.attributes["span_type"] == expected_span_type, msg
            if span != root_span:  # Non-root spans should have a parent
                assert span.attributes["function"]
            inputs = json.loads(span.attributes["inputs"])
            output = json.loads(span.attributes["output"])
            assert isinstance(inputs, dict)
            assert output is not None

    def validate_openai_tokens(self, span_list, is_stream):
        span_dict = {span.context.span_id: span for span in span_list}
        expected_tokens = {}
        for span in span_list:
            tokens = None
            # Validate the openai tokens are correctly set in the llm trace.
            if self._is_llm_span_with_tokens(span, is_stream):
                for token_name in LLM_TOKEN_NAMES + CUMULATIVE_LLM_TOKEN_NAMES:
                    assert token_name in span.attributes
                tokens = {token_name: span.attributes[token_name] for token_name in CUMULATIVE_LLM_TOKEN_NAMES}
            # Validate the openai tokens are correctly set in the embedding trace.
            if span.attributes.get("function", "") in EMBEDDING_FUNCTION_NAMES:
                for token_name in EMBEDDING_TOKEN_NAMES + CUMULATIVE_EMBEDDING_TOKEN_NAMES:
                    assert token_name in span.attributes
                tokens = {token_name: span.attributes[token_name] for token_name in CUMULATIVE_EMBEDDING_TOKEN_NAMES}
            # Aggregate the tokens to the parent span.
            if tokens is not None:
                current_span_id = span.context.span_id
                while True:
                    if current_span_id in expected_tokens:
                        expected_tokens[current_span_id] = {
                            key: expected_tokens[current_span_id][key] + tokens[key] for key in tokens
                        }
                    else:
                        expected_tokens[current_span_id] = tokens
                    parent_cxt = getattr(span_dict[current_span_id], "parent", None)
                    if parent_cxt is None:
                        break
                    current_span_id = parent_cxt.span_id
        # Validate the aggregated tokens are correctly set in the parent span.
        for span in span_list:
            span_id = span.context.span_id
            if span_id in expected_tokens:
                for token_name in expected_tokens[span_id]:
                    assert span.attributes[token_name] == expected_tokens[span_id][token_name]

    def _is_llm_span_with_tokens(self, span, is_stream):
        """
        This function checks if a given span is a LLM span with tokens.

        If in stream mode, the function checks if the span has attributes indicating it's an iterated span.
        In non-stream mode, it simply checks if the span's function attribute is in the list of LLM function names.

        Args:
            span: The span to check.
            is_stream: A boolean indicating whether the span is in stream mode.

        Returns:
            A boolean indicating whether the span is a LLM span with tokens.
        """
        if is_stream:
            return (
                span.attributes.get("function", "") in LLM_FUNCTION_NAMES
                and span.attributes.get("output_type", "") == "iterated"
            )
        else:
            return span.attributes.get("function", "") in LLM_FUNCTION_NAMES
