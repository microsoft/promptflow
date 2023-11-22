from promptflow import tool


@tool
def print_val(val):
    print(val)
    return val
