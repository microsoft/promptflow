from promptflow.contracts.multimedia import Image
from promptflow import tool


@tool
def python_with_image(image_dict: dict, logo_content: str) -> Image:
    image_dict["image_list2"] = [image_dict["image"], image_dict["image"]]
    image_dict["logo_content"] = logo_content
    return image_dict
