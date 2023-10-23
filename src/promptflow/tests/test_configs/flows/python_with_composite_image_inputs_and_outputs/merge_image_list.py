from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def merge_image_list(image_dict_1: dict,image_dict_2: dict) -> list:
    res = {}
    for k, v in image_dict_1.items():
        if k in image_dict_2:
            res[k] = _merge_image_list(v, image_dict_2[k])
    return res


def _merge_image_list(image_list_1: list[Image], image_list_2: list[Image]) -> list:
    hash_set = set()
    res = []
    for item in image_list_1 + image_list_2:
        if item._hash not in hash_set:
            hash_set.add(item._hash)
            res.append(item)
    return res
