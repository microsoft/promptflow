import json
from enum import Enum
from pathlib import Path

import pytest

from promptflow._constants import ICON, ICON_DARK, ICON_LIGHT
from promptflow._core.tool import DynamicList, GeneratedBy, InputSetting
from promptflow._core.tool_settings_parser import _parser_tool_icon, _parser_tool_input_settings
from promptflow.exceptions import UserErrorException

TEST_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.mark.unittest
class TestToolSettingsParser:
    def test_parser_input_settings(self):
        def mock_func(input_prefix: str):
            pass

        class UserType(str, Enum):
            STUDENT = "student"
            TEACHER = "teacher"

        input_dynamic_list_setting = DynamicList(function=mock_func, input_mapping={"prefix": "input_prefix"})
        generated_by_settings = GeneratedBy(
            function=mock_func,
            reverse_function=mock_func,
            input_settings={
                "index_type": InputSetting(dynamic_list=DynamicList(function=mock_func)),
                "index": InputSetting(
                    enabled_by="index_type",
                    enabled_by_value=["Workspace MLIndex"],
                    dynamic_list=DynamicList(function=mock_func),
                ),
            },
        )
        tool_inputs = {
            "teacher_id": {"type": "string"},
            "student_id": {"type": "string"},
            "dynamic_list_input": {"type": "string"},
            "generated_by_input": {"type": "string"},
        }
        input_settings = {
            "teacher_id": InputSetting(enabled_by="user_type", enabled_by_value=[UserType.TEACHER]),
            "student_id": InputSetting(enabled_by="user_type", enabled_by_value=[UserType.STUDENT]),
            "dynamic_list_input": InputSetting(
                dynamic_list=input_dynamic_list_setting,
                allow_manual_entry=True,
                is_multi_select=True,
            ),
            "generated_by_input": InputSetting(generated_by=generated_by_settings),
        }
        _parser_tool_input_settings(tool_inputs, input_settings)
        tool_inputs = json.loads(json.dumps(tool_inputs))
        expect_tool_inputs = {
            "teacher_id": {"type": "string", "enabled_by": "user_type", "enabled_by_value": ["teacher"]},
            "student_id": {"type": "string", "enabled_by": "user_type", "enabled_by_value": ["student"]},
            "dynamic_list_input": {
                "type": "string",
                "is_multi_select": True,
                "allow_manual_entry": True,
                "dynamic_list": {
                    "func_path": "executor.unittests._core.test_tool_settings_parser.mock_func",
                    "func_kwargs": [{"name": "input_prefix", "type": ["string"], "optional": False}],
                },
            },
            "generated_by_input": {
                "type": "string",
                "generated_by": {
                    "func_path": "executor.unittests._core.test_tool_settings_parser.mock_func",
                    "func_kwargs": [
                        {
                            "name": "input_prefix",
                            "type": ["string"],
                            "reference": "${inputs.input_prefix}",
                            "optional": False,
                        }
                    ],
                    "reverse_func_path": "executor.unittests._core.test_tool_settings_parser.mock_func",
                },
            },
        }
        assert expect_tool_inputs == tool_inputs

    def test_parser_tool_icon(self):
        image_path = TEST_ROOT / "test_configs" / "datas" / "logo.png"
        extra_info = {
            ICON: image_path,
        }
        _parser_tool_icon(extra_info)
        assert extra_info[ICON].startswith("data:image/png")

        extra_info = {ICON_DARK: image_path, ICON_LIGHT: image_path}
        _parser_tool_icon(extra_info)
        assert extra_info["icon"]["dark"].startswith("data:image/png")
        assert extra_info["icon"]["light"].startswith("data:image/png")

        extra_info = {
            ICON: "not/exist/path",
        }
        with pytest.raises(UserErrorException) as ex:
            _parser_tool_icon(extra_info)
        assert ex.value.message == ("Cannot find the icon path not/exist/path.")
