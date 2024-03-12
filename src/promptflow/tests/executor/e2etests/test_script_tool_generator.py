from pathlib import Path

import pytest

from promptflow._core.tool_meta_generator import generate_tool_meta_dict_by_file
from promptflow.exceptions import UserErrorException

TEST_ROOT = Path(__file__).parent.parent.parent
TOOL_ROOT = TEST_ROOT / "test_configs" / "tools"


@pytest.mark.e2etest
class TestScriptToolGenerator:
    def test_generate_script_tool_meta_with_dynamic_list(self):
        tool_path = TOOL_ROOT / "tool_with_dynamic_list_input.py"
        tool_meta = generate_tool_meta_dict_by_file(tool_path.as_posix(), "python")
        expect_tool_meta = {
            "name": "tool_with_dynamic_list_input",
            "type": "python",
            "inputs": {
                "input_prefix": {"type": ["string"]},
                "input_text": {
                    "type": ["list"],
                    "is_multi_select": True,
                    "allow_manual_entry": True,
                    "dynamic_list": {
                        "func_path": f"{tool_path.absolute()}:my_list_func",
                        "func_kwargs": [
                            {
                                "name": "prefix",
                                "type": ["string"],
                                "reference": "${inputs.input_prefix}",
                                "optional": True,
                                "default": "",
                            },
                            {"name": "size", "type": ["int"], "default": 10, "optional": True},
                        ],
                    },
                },
                "endpoint_name": {
                    "type": ["string"],
                    "dynamic_list": {
                        "func_path": f"{tool_path.absolute()}:list_endpoint_names",
                        "func_kwargs": [
                            {
                                "name": "prefix",
                                "type": ["string"],
                                "reference": "${inputs.input_prefix}",
                                "optional": True,
                                "default": "",
                            }
                        ],
                    },
                },
            },
            "description": "This is my tool with dynamic list input",
            "source": tool_path.as_posix(),
            "function": "my_tool",
        }
        assert expect_tool_meta == tool_meta

    def test_generate_script_tool_meta_with_enabled_by_value(self):
        tool_path = (TOOL_ROOT / "tool_with_enabled_by_value.py").as_posix()
        tool_meta = generate_tool_meta_dict_by_file(tool_path, "python")
        expect_tool_meta = {
            "name": "tool_with_enabled_by_value",
            "type": "python",
            "inputs": {
                "user_type": {"type": ["string"], "enum": ["student", "teacher"]},
                "student_id": {"type": ["string"], "enabled_by": "user_type", "enabled_by_value": ["student"]},
                "teacher_id": {"type": ["string"], "enabled_by": "user_type", "enabled_by_value": ["teacher"]},
            },
            "description": "This is my tool with enabled by value",
            "source": tool_path,
            "function": "my_tool",
        }
        assert expect_tool_meta == tool_meta

    def test_generate_script_tool_meta_with_generated_by(self):
        tool_path = TOOL_ROOT / "tool_with_generated_by_input.py"
        tool_meta = generate_tool_meta_dict_by_file((tool_path).as_posix(), "python")
        expect_tool_meta = {
            "name": "tool_with_generated_by_input",
            "type": "python",
            "inputs": {
                "index_json": {
                    "type": ["string"],
                    "generated_by": {
                        "func_path": f"{tool_path.absolute()}:generate_index_json",
                        "func_kwargs": [
                            {
                                "name": "index_type",
                                "type": ["string"],
                                "reference": "${inputs.index_type}",
                                "optional": False,
                            },
                            {"name": "index", "type": ["string"], "reference": "${inputs.index}", "optional": True},
                            {
                                "name": "index_connection",
                                "type": ["CognitiveSearchConnection"],
                                "reference": "${inputs.index_connection}",
                                "optional": True,
                            },
                            {
                                "name": "index_name",
                                "type": ["string"],
                                "reference": "${inputs.index_name}",
                                "optional": True,
                            },
                            {
                                "name": "content_field",
                                "type": ["string"],
                                "reference": "${inputs.content_field}",
                                "optional": True,
                            },
                            {
                                "name": "embedding_field",
                                "type": ["string"],
                                "reference": "${inputs.embedding_field}",
                                "optional": True,
                            },
                            {
                                "name": "metadata_field",
                                "type": ["string"],
                                "reference": "${inputs.metadata_field}",
                                "optional": True,
                            },
                            {
                                "name": "semantic_configuration",
                                "type": ["string"],
                                "reference": "${inputs.semantic_configuration}",
                                "optional": True,
                            },
                            {
                                "name": "embedding_connection",
                                "type": ["AzureOpenAIConnection", "OpenAIConnection"],
                                "reference": "${inputs.embedding_connection}",
                                "optional": True,
                            },
                            {
                                "name": "embedding_deployment",
                                "type": ["string"],
                                "reference": "${inputs.embedding_deployment}",
                                "optional": True,
                            },
                        ],
                        "reverse_func_path": f"{tool_path.absolute()}:reverse_generate_index_json",
                    },
                },
                "queries": {"type": ["string"]},
                "top_k": {"type": ["int"]},
                "index_type": {
                    "dynamic_list": {"func_path": f"{tool_path.absolute()}:list_index_types"},
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
                "index": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Workspace MLIndex"],
                    "dynamic_list": {"func_path": f"{tool_path.absolute()}:list_indexes"},
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
                "index_connection": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "type": ["CognitiveSearchConnection"],
                    "input_type": "uionly_hidden",
                },
                "index_name": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
                "content_field": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "dynamic_list": {"func_path": f"{tool_path.absolute()}:list_fields"},
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
                "embedding_field": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "dynamic_list": {"func_path": f"{tool_path.absolute()}:list_fields"},
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
                "metadata_field": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "dynamic_list": {"func_path": f"{tool_path.absolute()}:list_fields"},
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
                "semantic_configuration": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "dynamic_list": {"func_path": f"{tool_path.absolute()}:list_semantic_configuration"},
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
                "embedding_connection": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "type": ["AzureOpenAIConnection", "OpenAIConnection"],
                    "input_type": "uionly_hidden",
                },
                "embedding_deployment": {
                    "enabled_by": "index_type",
                    "enabled_by_value": ["Azure Cognitive Search"],
                    "dynamic_list": {
                        "func_path": f"{tool_path.absolute()}:list_embedding_deployment",
                        "func_kwargs": [
                            {
                                "name": "embedding_connection",
                                "type": ["string"],
                                "reference": "${inputs.embedding_connection}",
                                "optional": False,
                            }
                        ],
                    },
                    "type": ["string"],
                    "input_type": "uionly_hidden",
                },
            },
            "description": "This is a tool with generated by input",
            "source": tool_path.as_posix(),
            "function": "my_tool",
        }
        assert expect_tool_meta == tool_meta

    def test_generate_script_tool_meta_with_invalid_icon(self):
        tool_path = (TOOL_ROOT / "tool_with_invalid_icon.py").as_posix()
        with pytest.raises(UserErrorException) as ex:
            generate_tool_meta_dict_by_file(tool_path, "python")
        assert "Tool validation failed: Cannot provide both `icon` and `icon_light` or `icon_dark`." in ex.value.message

    def test_generate_script_tool_meta_with_invalid_enabled_by(self):
        tool_path = (TOOL_ROOT / "tool_with_invalid_enabled_by.py").as_posix()
        with pytest.raises(UserErrorException) as ex:
            generate_tool_meta_dict_by_file(tool_path, "python")
        assert 'Cannot find the input "invalid_input" for the enabled_by of teacher_id.' in ex.value.message
        assert 'Cannot find the input "invalid_input" for the enabled_by of student_id.' in ex.value.message

    def test_generate_script_tool_meta_with_invalid_dynamic_list(self):
        tool_path = TOOL_ROOT / "tool_with_invalid_dynamic_list.py"
        with pytest.raises(UserErrorException) as ex:
            generate_tool_meta_dict_by_file(tool_path.as_posix(), "python")
        assert "Cannot find invalid_tool_input in tool inputs." in ex.value.message
        assert "Missing required input(s) of dynamic_list function: ['prefix']" in ex.value.message
        assert (
            f"Cannot find invalid_func_input in the inputs of dynamic_list func {tool_path.absolute()}:my_list_func"
            in ex.value.message
        )

    def test_generate_script_tool_meta_with_invalid_schema(self):
        tool_path = (TOOL_ROOT / "tool_with_invalid_schema.py").as_posix()
        with pytest.raises(UserErrorException) as ex:
            generate_tool_meta_dict_by_file(tool_path, "python")
        assert "1 is not of type 'string'" in ex.value.message
