from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def passthrough(input_image: Image) -> Image:
    return input_image
