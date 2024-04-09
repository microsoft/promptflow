from typing import List
from promptflow.core import tool
from promptflow.contracts.multimedia import Image


@tool
def aggregate(images: List[Image]):
    from promptflow.core import log_metric
    image_count = 0
    for image in images:
        if not isinstance(image, Image):
            print(f"Invalid image: {image}")
        else:
            image_count += 1
    log_metric(key="image_count", value=image_count)

    return image_count
