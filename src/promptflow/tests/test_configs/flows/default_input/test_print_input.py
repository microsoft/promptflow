from promptflow.core import tool


@tool
def test_print_input(input_str: str, input_bool: bool, input_list: list, input_dict: dict):
    assert not input_bool
    assert input_list == []
    assert input_dict == {}
    print(input_str)
    return input_str