from promptflow import tool


@tool
def passthrough_dict(image_list: list, image_dict: dict):
    return image_dict
