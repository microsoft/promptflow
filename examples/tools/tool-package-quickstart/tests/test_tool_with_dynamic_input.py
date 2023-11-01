from my_tool_package.tools.tool_with_dynamic_list_input import my_tool, my_list_func
from my_tool_package.tools.mlindex_tool import list_indexes


def test_my_tool():
    result = my_tool(input_text=["apple", "banana"], input_prefix="My")
    assert result == 'Hello My apple,banana'


def test_my_list_func():
    result = my_list_func(prefix="My")
    assert len(result) == 10
    assert "value" in result[0]


def test_list_indexes():
    result = list_indexes(
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-gallery",
        keyword="")
    print(len(result))
