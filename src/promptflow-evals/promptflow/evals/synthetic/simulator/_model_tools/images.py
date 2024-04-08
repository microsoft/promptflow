# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import os
import re
from typing import List, Optional

# Image types supported by Azure Cognitive Services: JPEG, PNG, GIF, BMP, WEBP, ICO, TIFF, or MPO format
IMAGE_TYPES = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "ico", "tiff", "mpo"]
MULTIMODAL_IMAGE_TYPES = ["png", "jpg", "jpeg", "gif"]

IMAGES_PATTERN = r"{\s*(image:[^}\s]+)\s*}"


# ================= Image Loading =================
def load_image_base64(image_path: str) -> str:
    import pybase64

    with open(image_path, "rb") as f:
        return pybase64.b64encode(f.read()).decode("utf-8")


def load_image_binary(image_path: str) -> bytes:
    with open(image_path, "rb") as f:
        return f.read()


# ================ Prompt Image Replacement ================
def replace_prompt_captions(
    prompt: str, captions: Optional[dict] = None, logger: logging.Logger = logging.getLogger("Prompt Image Captioner")
) -> str:
    """
    Insert captions for images into the prompt.

    :param prompt: The original prompt string.
    :type prompt: str
    :param captions: A dictionary containing image IDs as keys and their corresponding captions as values.
                     Defaults to None if no captions are provided.
    :type captions: Optional[dict]
    :param logger: A logger object for logging messages. Defaults to a logger named "Prompt Image Captioner".
    :type logger: logging.Logger
    :return: The prompt string with captions inserted, if captions are provided; otherwise, the original prompt string.
    :rtype: str
    """
    # Compile pattern if not already compiled
    _compile_prompt_images_pattern()

    if captions is None:
        captions = {}

    prompt_data = []
    for text_or_image in IMAGES_PATTERN.split(prompt):
        # If section is an image, try to load it or replace it with a caption
        if text_or_image.startswith("image:"):
            image_name = text_or_image[len("image:") :]

            if image_name in captions:
                prompt_data.append(_format_image_captions(image_name, captions))
            else:
                prompt_data.append(text_or_image)
                logger.warning(f"Image not found in captions: {image_name}")
        # If section is text, add it to the prompt
        elif text_or_image != "":
            prompt_data.append(text_or_image)
        else:
            # Empty strings means the image is at the start or end of the prompt
            pass

    return "".join(prompt_data)


def format_multimodal_prompt(
    prompt: str,
    images_dir: Optional[str] = None,
    captions: Optional[dict] = None,
    logger: logging.Logger = logging.getLogger("Prompt Image Formatter"),
) -> List[dict]:
    """
    Formats a prompt with images into a list of dictionaries for the API.

    :param prompt: The main text prompt.
    :type prompt: str
    :param images_dir: The directory containing images to be included in the prompt, if any. Default is None.
    :type images_dir: Optional[str]
    :param captions: A dictionary mapping image filenames to their corresponding captions, if available.
    :type captions: Optional[Dict[str, str]]
    :param logger: The logger object to log messages. Default is a logger named "Prompt Image Formatter".
    :type logger: logging.Logger
    :return: A list of dictionaries representing the formatted prompt for the API.
    :rtype: List[dict]
    """
    # Compile pattern if not already compiled
    _compile_prompt_images_pattern()

    if captions is None:
        captions = {}

    # Split prompt into text and image sections
    prompt_data = []
    for text_or_image in IMAGES_PATTERN.split(prompt):
        image_name = text_or_image[len("image:") :]

        # If section is an image, load it
        if text_or_image.startswith("image:"):
            # Get image location
            image_loc = image_name
            if not os.path.exists(image_name) and images_dir is not None:
                image_loc = os.path.join(images_dir, image_name)

            # If image is found, add it to the transcript
            if os.path.exists(image_loc) and image_name.split(".")[-1].lower() in MULTIMODAL_IMAGE_TYPES:
                image_data = load_image_base64(image_loc)
                prompt_data.append({"type": "image", "data": image_data})
            # If image is not found, check in captions
            elif image_name in captions:
                prompt_data.append({"type": "text", "data": _format_image_captions(image_name, captions)})
                logger.warning(f"Image location not found, but captions were found for: {image_loc}")
            else:
                raise ValueError(
                    f"Image location and captions not found for: {image_loc}.  Found images: {os.listdir(images_dir)}"
                )
        # If section is text, add it to the prompt
        elif text_or_image != "":
            prompt_data.append({"type": "text", "data": text_or_image})
        else:
            # Empty strings means the image is at the start or end of the prompt
            pass

    return prompt_data


def _compile_prompt_images_pattern() -> None:
    global IMAGES_PATTERN  # pylint: disable=global-statement
    if isinstance(IMAGES_PATTERN, str):
        images_pattern_text: str = IMAGES_PATTERN
        IMAGES_PATTERN = re.compile(images_pattern_text)  # type: ignore[assignment]


def _format_image_captions(image_name, captions):
    """
    Format image captions for images inserted into completions as natural language.

    :param image_name: The name of the image.
    :type image_name: str
    :param captions: A dictionary containing image captions where keys are image names and values are captions.
    :type captions: Dict[str, str]
    :return: A formatted string representing the image caption.
    :rtype: str
    """
    return f"```image:{image_name}\n{captions[image_name]}\n```" ""
