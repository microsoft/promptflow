from promptflow import tool


@tool
def merge_images(image_list: list, image_dict: list):
    res = set()
    for item in image_list[0]:
        res.add(item)
    for _, v in image_dict[0].items():
        res.add(v)
    return list(res)
