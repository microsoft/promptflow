import os

import pytest

from promptflow.executor import FlowExecutor

from ...utils import get_flow_configs, get_flow_folder, get_yaml_file
from ..asserter import LineResultAsserter, RunTrackerAsserter, run_assertions


@pytest.mark.e2etest
class TestExecutor:
    @pytest.mark.parametrize(
        "flow_folder",
        [
            "async_tools",
        ],
    )
    def test_executor_exec_line(self, flow_folder, dev_connections):
        os.chdir(get_flow_folder(flow_folder))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        line_result = executor.exec_line({"input_str": "Hello"})

        configs = get_flow_configs("async_tools")
        for asserter_type in configs["assertions"].keys():
            if asserter_type == "line_result":
                asserter = LineResultAsserter(line_result, node_count=len(executor._flow.nodes))
                run_assertions(asserter, configs["assertions"]["line_result"])
            elif asserter_type == "run_tracker":
                asserter = RunTrackerAsserter(executor._run_tracker)
                run_assertions(asserter, configs["assertions"]["run_tracker"])
