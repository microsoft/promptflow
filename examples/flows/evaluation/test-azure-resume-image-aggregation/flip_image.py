import io
from promptflow import tool
from promptflow.contracts.multimedia import Image
from PIL import Image as PIL_Image


@tool
def passthrough(input_image: Image, fail_google_before: str) -> Image:
    from datetime import datetime
    hour = datetime.now().hour
    minute = datetime.now().minute
    hour_minute_str = f"{hour}".zfill(2) + f"{minute}".zfill(2)

    if "google" in input_image.source_url:
        if hour_minute_str < fail_google_before:
            raise Exception("Google failure")

    image_stream = io.BytesIO(input_image)
    pil_image = PIL_Image.open(image_stream)
    flipped_image = pil_image.transpose(PIL_Image.FLIP_LEFT_RIGHT)
    buffer = io.BytesIO()
    flipped_image.save(buffer, format="PNG")
    return Image(buffer.getvalue(), mime_type="image/png")
