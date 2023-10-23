from promptflow.contracts.multimedia import Image
from promptflow import tool


@tool
def python_with_image(image: Image, image_name: str) -> Image:
    return {"image": image, "image_name": image_name, "image_list": [image, image]}
