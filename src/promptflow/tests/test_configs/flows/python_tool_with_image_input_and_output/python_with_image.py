from promptflow.contracts.multimedia import Image
from promptflow import tool


@tool
def python_with_image(image: Image) -> Image:
    return image
