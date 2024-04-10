from enum import Enum

from promptflow.entities import InputSetting
from promptflow.core import tool


class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


@tool(name=1, description=1)
def invalid_schema_type(input1: str) -> str:
    return 'hello ' + input1


@tool(
    name="invalid_input_settings",
    description="This is my tool with enabled by value",
    input_settings={
        "teacher_id": InputSetting(enabled_by="invalid_input", enabled_by_value=[UserType.TEACHER]),
        "student_id": InputSetting(enabled_by="invalid_input", enabled_by_value=[UserType.STUDENT]),
    }
)
def invalid_input_settings(user_type: UserType, student_id: str = "", teacher_id: str = "") -> str:
    pass


@tool(name="invalid_tool_icon", icon="mock_icon_path", icon_dark="mock_icon_path", icon_light="mock_icon_path")
def invalid_tool_icon(input1: str) -> str:
    return 'hello ' + input1
