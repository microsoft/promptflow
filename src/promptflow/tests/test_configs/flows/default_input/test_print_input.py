from promptflow import tool


@tool
def test_print_input(input: str):
    print(input)
    return input