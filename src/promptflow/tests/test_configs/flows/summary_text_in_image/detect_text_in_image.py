# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import easyocr
import tempfile

from promptflow._core.tool import tool
from promptflow.contracts.multimedia import Image
from promptflow._utils.multimedia_utils import _save_image_to_file

@tool
def detect_text_in_image(image: Image) -> str:

    with tempfile.TemporaryDirectory() as temp_folder:
        _save_image_to_file(image=image, file_name="image", folder_path=temp_folder)

        reader = easyocr.Reader(['en'])
        result = reader.readtext(os.path.join(temp_folder, "image.png"), detail=0)
        return "\n".join(result)
