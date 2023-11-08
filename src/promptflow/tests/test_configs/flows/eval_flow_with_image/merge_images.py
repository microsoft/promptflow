from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def merge_images(image: list, image_list: list, image_dict: list):
    res = set()
    res.add(image[0])
    for item in image_list[0]:
        res.add(item)
    for _, v in image_dict[0].items():
        res.add(v)
    return list(res)
