from promptflow import tool


@tool
def conditional_node(message: str):
    return message + "\nExecute the conditional_node"
