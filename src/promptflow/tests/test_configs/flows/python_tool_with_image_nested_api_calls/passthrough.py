from promptflow.core import tool


@tool
def passthrough(image, call_passthrough: bool = True):
    if call_passthrough:
        image = passthrough(image, False)
    return image
