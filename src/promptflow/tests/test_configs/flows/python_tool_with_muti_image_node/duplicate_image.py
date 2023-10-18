from promptflow.contracts.multimedia import Image
from promptflow import tool


@tool
def duplicate_image(image: Image, name: str) -> list[Image]:
    return [image, image, name]
