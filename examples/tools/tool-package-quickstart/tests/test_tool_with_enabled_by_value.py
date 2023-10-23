from my_tool_package.tools.tool_with_enabled_by_value import my_tool


def test_my_tool():
    result = my_tool(user_type="student", student_id="123", teacher_id=None)
    assert result == '123'
