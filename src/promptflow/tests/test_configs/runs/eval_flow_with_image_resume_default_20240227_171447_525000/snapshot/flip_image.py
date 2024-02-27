import io
from pathlib import Path
from promptflow import tool
from promptflow.contracts.multimedia import Image
from PIL import Image as PIL_Image


@tool
def passthrough(input_image: Image) -> Image:
    switch_file = Path("google_failure_switch.txt")
    if "google" in input_image.source_url:
        if switch_file.exists():
            switch_file.unlink()
            raise Exception("Google failure")
        else:
            switch_file.touch()

    image_stream = io.BytesIO(input_image)
    pil_image = PIL_Image.open(image_stream)
    flipped_image = pil_image.transpose(PIL_Image.FLIP_LEFT_RIGHT)
    buffer = io.BytesIO()
    flipped_image.save(buffer, format="PNG")
    return Image(buffer.getvalue(), mime_type="image/png")
