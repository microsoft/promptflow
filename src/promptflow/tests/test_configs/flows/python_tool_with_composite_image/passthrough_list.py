from promptflow.core import tool

@tool
def passthrough_list(image_list: list, image_dict: dict):
    return image_list
