# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import io
from pathlib import Path

from promptflow._constants import ICON, ICON_DARK, ICON_LIGHT
from promptflow._utils.tool_utils import asdict_without_none
from promptflow.contracts.multimedia import Image
from promptflow.exceptions import UserErrorException


def _parser_tool_input_settings(tool_inputs, input_settings):
    """
    Parser input settings to dict

    :param tool_inputs: Tool inputs
    :type tool_inputs: Dict[str, obj]
    :param input_settings: Input settings of the tool
    :type input_settings: Dict[str, obj]
    """
    generated_by_inputs = {}
    for input_name, settings in input_settings.items():
        tool_inputs[input_name].update(asdict_without_none(settings))
        kwargs = settings._kwargs or {}
        for k, v in kwargs.items():
            if k in tool_inputs[input_name]:
                if isinstance(v, dict):
                    tool_inputs[input_name][k].update(v)
                elif isinstance(v, list):
                    tool_inputs[input_name][k].append(v)
                else:
                    tool_inputs[input_name][k] = v
            else:
                tool_inputs[input_name][k] = v
        if settings.generated_by:
            generated_by_inputs.update(settings.generated_by._input_settings)
    tool_inputs.update(generated_by_inputs)


def _parser_tool_icon(extra_info):
    """parser tool icon to base64."""
    if ICON in extra_info:
        extra_info[ICON] = _serialize_icon_data(extra_info[ICON])
    if ICON_LIGHT in extra_info:
        icon = extra_info.get(ICON, {})
        icon["light"] = _serialize_icon_data(extra_info.pop(ICON_LIGHT))
        extra_info[ICON] = icon
    if ICON_DARK in extra_info:
        icon = extra_info.get(ICON, {})
        icon["dark"] = _serialize_icon_data(extra_info.pop(ICON_DARK))
        extra_info[ICON] = icon
    return extra_info


def _serialize_icon_data(icon):
    if not Path(icon).exists():
        raise UserErrorException(f"Cannot find the icon path {icon}.")
    return _serialize_image_data(icon)


def _serialize_image_data(image_path):
    """Serialize image to base64."""
    from PIL import Image as PIL_Image

    with open(image_path, "rb") as image_file:
        # Create a BytesIO object from the image file
        image_data = io.BytesIO(image_file.read())

    # Open the image and resize it
    img = PIL_Image.open(image_data)
    if img.size != (16, 16):
        img = img.resize((16, 16), PIL_Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    icon_image = Image(buffered.getvalue(), mime_type="image/png")
    image_url = icon_image.to_base64(with_type=True)
    return image_url
