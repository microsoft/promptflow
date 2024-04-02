import uuid

import pytest

from promptflow.executor import FlowExecutor
from promptflow.executor._result import LineResult

from ...utils import get_flow_configs, get_yaml_file, prepare_memory_exporter
from ..asserter import OtelTraceAsserter, run_assertions
from ..process_utils import execute_function_in_subprocess


def get_chat_input(stream):
    return {
        "question": "What is the capital of the United States of America?",
        "chat_history": [],
        "stream": stream,
    }


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestOTelTracer:
    @pytest.mark.parametrize(
        "flow_file, inputs, is_stream",
        [
            ("openai_chat_api_flow", get_chat_input(False), False),
        ],
    )
    def test_otel_trace_with_llm(
        self,
        dev_connections,
        flow_file,
        inputs,
        is_stream,
    ):
        execute_function_in_subprocess(
            self.assert_otel_traces_with_llm,
            dev_connections,
            flow_file,
            inputs,
            is_stream,
        )

    def assert_otel_traces_with_llm(self, dev_connections, flow_file, inputs, is_stream):
        memory_exporter = prepare_memory_exporter()

        line_result, line_run_id = self.submit_flow_run(flow_file, inputs, dev_connections)
        assert isinstance(line_result, LineResult)
        assert isinstance(line_result.output, dict)

        span_list = memory_exporter.get_finished_spans()
        configs = get_flow_configs("openai_chat_api_flow")
        for asserter_type in configs["assertions"].keys():
            if asserter_type == "otel_trace":
                asserter = OtelTraceAsserter(span_list, line_run_id, is_batch=False, is_stream=False)
                run_assertions(asserter, configs["assertions"]["otel_trace"])

    def submit_flow_run(self, flow_file, inputs, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_file), dev_connections)
        line_run_id = str(uuid.uuid4())
        line_result = executor.exec_line(inputs, run_id=line_run_id)
        return line_result, line_run_id
