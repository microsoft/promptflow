from types import GeneratorType

import pytest

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor

from ..utils import get_yaml_file


@pytest.mark.usefixtures("dev_connections")
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
            "openai.api_resources.chat_completion.ChatCompletion.create",
            "openai.api_resources.completion.Completion.create",
            "openai.api_resources.embedding.Embedding.create",
            "openai.resources.completions.Completions.create",  # openai>=1.0.0
            "openai.resources.chat.completions.Completions.create",  # openai>=1.0.0
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

    def get_chat_input(stream):
        return {
            "question": "What is the capital of the United States of America?",
            "chat_history": [],
            "stream": stream,
        }

    def get_comletion_input(stream):
        return {"prompt": "What is the capital of the United States of America?", "stream": stream}

    @pytest.mark.parametrize(
        "flow_folder, inputs",
        [
            ("openai_chat_api_flow", get_chat_input(False)),
            ("openai_chat_api_flow", get_chat_input(True)),
            ("openai_completion_api_flow", get_comletion_input(False)),
            ("openai_completion_api_flow", get_comletion_input(True)),
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

        assert "total_tokens" in flow_result.run_info.system_metrics
        assert flow_result.run_info.system_metrics["total_tokens"] > 0

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

        tool_trace = flow_result.run_info.api_calls[0]
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
        tool_trace = flow_result.run_info.api_calls[0]
        generator_output_trace = tool_trace.get("output")

        # Verify that the trace output is a list
        assert isinstance(generator_output_trace, list)
        if allow_generator_output:
            # If generator output is allowed, the trace list should be empty before consumption
            assert not generator_output_trace
            # Obtain the generator from the flow result
            answer_gen = flow_result.output.get("answer")
            assert isinstance(answer_gen, GeneratorType)
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
