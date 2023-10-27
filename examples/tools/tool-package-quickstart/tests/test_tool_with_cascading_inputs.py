from my_tool_package.tools.tool_with_cascading_inputs import my_tool


def test_my_tool():
    result = my_tool(user_type="student", student_id="student_id")
    assert result == '123'
