from promptflow.core import tool
from promptflow.contracts.multimedia import Image


@tool
def merge_images(image_list: list, image_dict: list):
    res = set()
    for item in image_list[0]:
        res.add(item)
    for _, v in image_dict[0].items():
        res.add(v)
    assert all(isinstance(item, Image) for item in res)
    return list(res)
