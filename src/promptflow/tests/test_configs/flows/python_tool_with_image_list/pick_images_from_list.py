from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def pick_images_from_list(image_list: list[Image], idx_l: int, idx_r: int) -> list[Image]:
    if idx_l <= idx_r and idx_l >= 0 and idx_r < len(image_list):
        return image_list[idx_l:idx_r + 1]
    else:
        raise Exception(f"Invalid index.")
