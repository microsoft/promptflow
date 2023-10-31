from enum import Enum

from promptflow._core.tool import InputSettings, tool


class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


@tool(
    name="My Tool with Enabled By Value",
    description="This is my tool with enabled by value",
    input_settings={"teacher_id": InputSettings(enabled_by="user_type", enabled_by_value=[UserType.TEACHER])}
)
def my_tool(user_type: Enum, student_id: str = "", teacher_id: str = "") -> str:
    """This is a dummy function to support enabled by feature.

    :param user_type: user type, student or teacher.
    :param student_id: student id.
    :param teacher_id: teacher id.
    :return: id of the user.
    If user_type is student, return student_id.
    If user_type is teacher, return teacher_id.
    """
    if user_type == UserType.STUDENT:
        return student_id
    elif user_type == UserType.TEACHER:
        return teacher_id
    else:
        raise Exception("Invalid user.")
