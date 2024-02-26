from enum import Enum

from promptflow.entities import InputSetting
from promptflow._core.tool import tool


class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


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
