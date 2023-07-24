import json
from pathlib import Path

import pytest

from promptflow.contracts.flow import Flow, InputAssignment, InputValueType
from promptflow.contracts.tool import Tool, ToolType, ValueType

TEST_ROOT = Path(__file__).parent.parent.parent

default_llm_tool_dict = {
    "name": "title_generation_tool_1",
    "type": "LLM",
    "description": "Generates a short title for the given Text",
    "prompt_type": "completion",
    "inputs": {
        "i": {
            "type": "string",
        }
    },
}


@pytest.mark.unittest
class TestContractDeserialization:
    @pytest.mark.parametrize(
        "type_str, expected",
        [
            ("String", ValueType.STRING),
            ("string", ValueType.STRING),
            ("STRING", ValueType.STRING),
            ("int", ValueType.INT),
            ("Int", ValueType.INT),
            ("INT", ValueType.INT),
            ("double", ValueType.DOUBLE),
            ("Double", ValueType.DOUBLE),
            ("DOUBLE", ValueType.DOUBLE),
        ],
    )
    def test_value_type_enum(self, type_str, expected):
        d = default_llm_tool_dict.copy()
        d["inputs"]["i"]["type"] = type_str
        tool = Tool.deserialize(d)
        assert expected == tool.inputs["i"].type[0]

    @pytest.mark.parametrize(
        "type_str, expected",
        [
            ("LLM", ToolType.LLM),
            ("llm", ToolType.LLM),
            ("Llm", ToolType.LLM),
            ("PROMPT", ToolType.PROMPT),
            ("prompt", ToolType.PROMPT),
            ("PYTHON", ToolType.PYTHON),
            ("python", ToolType.PYTHON),
            ("Python", ToolType.PYTHON),
        ],
    )
    def test_tool_type(self, type_str, expected):
        d = default_llm_tool_dict.copy()
        d["type"] = type_str
        tool = Tool.deserialize(d)
        assert expected == tool.type

    @pytest.mark.parametrize(
        "value, type, property, section, expected",
        [
            ("${n0}", InputValueType.NODE_REFERENCE, "", "output", "${n0.output}"),
            ("${n0.output}", InputValueType.NODE_REFERENCE, "", "output", ""),
            ("${n0.prompt}", InputValueType.NODE_REFERENCE, "", "prompt", ""),
            ("${n0.output.answer}", InputValueType.NODE_REFERENCE, "answer", "output", ""),
            ("${n0.zzz.vvv}", InputValueType.NODE_REFERENCE, "vvv", "zzz", ""),
            ("${n0.output.answer.value}", InputValueType.NODE_REFERENCE, "answer.value", "output", ""),
            ("${flow.input0}", InputValueType.FLOW_INPUT, "", "", ""),
            ("12345", InputValueType.LITERAL, "", "", ""),
        ],
    )
    def test_input_assignment(self, value, type, property, section, expected):
        assignment = InputAssignment.deserialize(value)
        assert type == assignment.value_type, f"ValueType: expected {type} but got {assignment.value_type}"
        assert property == assignment.property, f"Property: expected {property} but got {assignment.property}"
        assert section == assignment.section, f"Section: expected {section} but got {assignment.section}"
        if not expected:
            expected = value
        serialized = assignment.serialize()
        assert expected == serialized, f"Serialized: expected {expected} but got {serialized}"

    def test_flow_deserialize(self) -> None:
        model_dir = TEST_ROOT / "test_configs/e2e_samples/qa_with_bing"
        flow_file = model_dir / "flow.json"
        flow_json_dict = json.loads(open(flow_file, "r").read())
        flow = Flow.deserialize(flow_json_dict)
        assert isinstance(flow, Flow)
        # Update to an unknown tool package
        flow_json_dict["tools"][1]["module"] = "mock_module"
        with pytest.raises(
            Exception, match=r"failed. Root cause: ModuleNotFoundError\(\"No module named 'mock_module'\"\)"
        ):
            Flow.deserialize(flow_json_dict)
