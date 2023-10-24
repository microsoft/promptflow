import random

from promptflow.contracts.multimedia import Image
from promptflow import tool


@tool
def pick_an_image(image_1: Image, image_2: Image) -> Image:
    if random.choice([True, False]):
        return image_1
    else:
        return image_2
