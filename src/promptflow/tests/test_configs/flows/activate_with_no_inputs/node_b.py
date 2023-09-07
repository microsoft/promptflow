from promptflow import tool


@tool
def my_python_tool():
    print("Avtivate")
    return 'Executing...'
