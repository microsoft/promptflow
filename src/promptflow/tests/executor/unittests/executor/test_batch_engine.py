from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.executor.batch_engine import BatchEngine
from promptflow.executor.flow_executor import FlowExecutor

from ...utils import get_yaml_file

# from unittest.mock import MagicMock

FLOW_FOLDER = "python_tool_with_image_input_and_output"


@pytest.mark.unittest
class TestBatchEngine:
    def setup_method(self):
        # Define mock objects and methods
        flow_file = get_yaml_file(FLOW_FOLDER)
        self.flow_executor = FlowExecutor.create(flow_file, {})
        self.batch_engine = BatchEngine(self.flow_executor)

    def test_get_input_dicts(self):
        pass

    def test_resolve_data(self):
        pass

    def test_resolve_dir(self):
        pass

    def test_resolve_image(self):
        pass

    def test_persist_outputs(self):
        expected_outputs = [
            {"line_number": 0, "output": {"data:image/jpg;path": "output_1.jpg"}},
            {"line_number": 1, "output": {"data:image/jpg;path": "output_2.jpg"}},
        ]
        output_dir = Path(mkdtemp())
        actual_outputs = self.batch_engine._persist_outputs(expected_outputs, output_dir)
        assert actual_outputs == expected_outputs
        assert (output_dir / "output.jsonl").exists()
