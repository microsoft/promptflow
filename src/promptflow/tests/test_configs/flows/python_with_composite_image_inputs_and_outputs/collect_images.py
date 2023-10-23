from typing import Any

from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def collect_images(
    image_list: list,
    image_dict: dict
) -> list[Image]:
    return {
        "image_from_list": _get_images_value(image_list),
        "image_from_dict": _get_images_value(image_dict),
    }


def _get_images_value(value: Any) -> list[Image]:
    res = []
    if isinstance(value, Image):
        return [value]
    elif isinstance(value, list):
        for item in value:
            res.extend(_get_images_value(item))
    elif isinstance(value, dict):
        for _, v in value.items():
            res.extend(_get_images_value(v))
    return res
