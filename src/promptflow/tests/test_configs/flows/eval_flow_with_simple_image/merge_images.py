from promptflow.core import tool


@tool
def merge_images(image_1: list, image_2: list, image_3: list):
    res = set()
    res.add(image_1[0])
    res.add(image_2[0])
    res.add(image_3[0])
    return list(res)
