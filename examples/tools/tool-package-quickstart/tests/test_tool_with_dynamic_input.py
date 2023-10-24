from my_tool_package.tools.tool_with_dynamic_list_input import my_tool, my_list_func


def test_my_tool():
    result = my_tool(input_text=["apple", "banana"], input_prefix="My")
    assert result == 'Hello My apple,banana'


def test_my_list_func():
    result = my_list_func(prefix="My")
    assert len(result) == 10
    assert "value" in result[0]
