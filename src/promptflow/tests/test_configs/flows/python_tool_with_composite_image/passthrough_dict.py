from promptflow import tool


@tool
def passthrough_dict(image_list: list,image_dict: dict) -> list:
    return image_dict
