from promptflow._core.tool import tool
from enum import Enum

from promptflow._core.tool import InputSetting


class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


@tool(
    description="tool with input settings",
    input_settings={
        "teacher_id": InputSetting(enabled_by="user_type", enabled_by_value=[UserType.TEACHER]),
        "student_id": InputSetting(enabled_by="user_type", enabled_by_value=[UserType.STUDENT],
                                   undefined_field={"key": "value"}),
    },
    unknown_key="value",
)
def tool_with_input_settings(user_type: UserType, student_id: str = "", teacher_id: str = "") -> str:
    if user_type == UserType.STUDENT:
        return student_id
    elif user_type == UserType.TEACHER:
        return teacher_id
    else:
        raise Exception("Invalid user.")
