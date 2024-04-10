from promptflow.core import tool
from promptflow.contracts.multimedia import Image

@tool
def passthrough_list(image_list: list, image_dict: dict):
    assert all(isinstance(item, Image) for item in image_list)
    return image_list
