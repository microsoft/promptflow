import uuid
from types import GeneratorType

import pytest

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.exceptions import UserErrorException
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import ConnectionNotFound, InputTypeError, ResolveToolError
from promptflow.executor.flow_executor import BulkResult, LineResult
from promptflow.storage import AbstractRunStorage
from promptflow.executor.batch_engine import PythonExecutor, NewBatchEngine

from ..utils import (
    get_yaml_file,
    get_flow_sample_inputs,
)


class MemoryRunStorage(AbstractRunStorage):
    def __init__(self):
        self._node_runs = {}
        self._flow_runs = {}

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._flow_runs[run_info.run_id] = run_info

    def persist_node_run(self, run_info: NodeRunInfo):
        self._node_runs[run_info.run_id] = run_info


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestBatchEngine:
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
        ["prompt_tools"],
    )
    def test_executor_exec_bulk(self, flow_folder, dev_connections):
        NewBatchEngine.register_executor("python", PythonExecutor)
        yaml_file = get_yaml_file(flow_folder)
        engine = NewBatchEngine(yaml_file, MemoryRunStorage())
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        from pathlib import Path
        from tempfile import mkdtemp
        import json
        input_dir = Path(mkdtemp())
        output_dir = Path(mkdtemp())
        with open(input_dir / "inputs.jsonl", "w") as fout:
            for i in bulk_inputs:
                fout.write(json.dumps(i) + "\n")
        nlines = len(bulk_inputs)
        bulk_results = engine.run(
            {"data": str(input_dir)}, inputs_mapping={"text": "${data.text}"},
            output_dir=output_dir, run_id=run_id
        )
        assert isinstance(bulk_results, BulkResult)
        msg = f"Bulk result only has {len(bulk_results.line_results)}/{nlines} outputs"
        assert len(bulk_results.outputs) == nlines, msg
        for i, output in enumerate(bulk_results.outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
        msg = f"Bulk result only has {len(bulk_results.line_results)}/{nlines} line results"
        assert len(bulk_results.outputs) == nlines, msg
        for i, line_result in enumerate(bulk_results.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.status == Status.Completed, f"{i}th line got {line_result.run_info.status}"
