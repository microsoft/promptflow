from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def pick_images_from_list(
    image_list: list[Image],
    image_list_2: list[Image],
    image_dict: dict,
    idx_1: int,
    idx_2: int
) -> list[Image]:
    if idx_1 >= 0 and idx_1 < len(image_list) and idx_2 >= 0 and idx_2 < len(image_list_2):
        return {"Image list": [image_list[idx_1], image_list_2[idx_2]], "Image dict": image_dict}
    else:
        raise Exception(f"Invalid index.")
