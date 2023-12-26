import base64
import os
import re
import uuid
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict
from urllib.parse import urlparse

import filetype
import requests

from promptflow._utils._errors import InvalidImageInput, LoadMultimediaDataError
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.multimedia import Image, PFBytes, Text
from promptflow.contracts.tool import ValueType
from promptflow.exceptions import ErrorTarget

MIME_PATTERN = re.compile(r"^data:image/(.*);(path|base64|url)$")


def _get_mime_type_from_path(path: Path):
    ext = path.suffix[1:]
    return f"image/{ext}" if ext else "image/*"


def _get_extension_from_mime_type(mime_type: str):
    ext = mime_type.split("/")[-1]
    if ext == "*":
        return None
    return ext


def is_multimedia_dict(multimedia_dict: dict):
    if len(multimedia_dict) != 1:
        return False
    key = list(multimedia_dict.keys())[0]
    if re.match(MIME_PATTERN, key):
        return True
    return False


def is_multimedia_dict_v2(multimedia_dict: dict):
    if len(multimedia_dict) != 2:
        return False
    if "type" not in multimedia_dict:
        return False
    image_type = multimedia_dict["type"]
    if image_type in ["image_url", "image_file"] and image_type in multimedia_dict:
        return True
    return False


def is_text_dict(text_dict: dict):
    if len(text_dict) != 2:
        return False
    if "type" not in text_dict:
        return False
    if text_dict["type"] == "text" and "text" in text_dict:
        text = text_dict["text"]
        if isinstance(text, str):
            return True
        elif isinstance(text, dict):
            if "value" in text and isinstance(text["value"], str):
                return True
    return False


def _get_multimedia_info(key: str):
    match = re.match(MIME_PATTERN, key)
    if match:
        return match.group(1), match.group(2)
    return None, None


def _is_url(value: str):
    try:
        result = urlparse(value)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def _is_base64(value: str):
    prefix_regex = re.compile(r"^data:image/(.*);base64")
    base64_regex = re.compile(r"^([A-Za-z0-9+/]{4})*(([A-Za-z0-9+/]{2})*(==|[A-Za-z0-9+/]=)?)?$")
    base64_with_prefix = value.split(",")
    if len(base64_with_prefix) == 2:
        if re.match(prefix_regex, base64_with_prefix[0]) and re.match(base64_regex, base64_with_prefix[1]):
            return True
    elif len(base64_with_prefix) == 1:
        if re.match(base64_regex, value):
            return True
    return False


def _create_image_from_file(f: Path, mime_type: str = None):
    if not mime_type:
        mime_type = _get_mime_type_from_path(f)
    with open(f, "rb") as fin:
        return Image(fin.read(), mime_type=mime_type)


def _create_image_from_base64(base64_str: str, mime_type: str = None):
    base64_str = base64_str.split(",")[-1]
    image_bytes = base64.b64decode(base64_str)
    if not mime_type:
        mime_type = filetype.guess_mime(image_bytes)
        if not mime_type.startswith("image/"):
            mime_type = "image/*"
    return Image(image_bytes, mime_type=mime_type)


def _create_image_from_url(url: str, mime_type: str = None):
    response = requests.get(url)
    if response.status_code == 200:
        if not mime_type:
            mime_type = filetype.guess_mime(response.content)
            if not mime_type.startswith("image/"):
                mime_type = "image/*"
        return Image(response.content, mime_type=mime_type, source_url=url)
    else:
        raise InvalidImageInput(
            message_format="Failed to fetch image from URL: {url}. Error code: {error_code}. "
            "Error message: {error_message}.",
            target=ErrorTarget.EXECUTOR,
            url=url,
            error_code=response.status_code,
            error_message=response.text,
        )


def _create_image_from_dict_v1(image_dict: dict):
    for k, v in image_dict.items():
        format, resource = _get_multimedia_info(k)
        if resource == "path":
            return _create_image_from_file(Path(v), mime_type=f"image/{format}")
        elif resource == "base64":
            if _is_base64(v):
                return _create_image_from_base64(v, mime_type=f"image/{format}")
            else:
                raise InvalidImageInput(
                    message_format=f"Invalid base64 image: {v}.",
                    target=ErrorTarget.EXECUTOR,
                )
        elif resource == "url":
            return _create_image_from_url(v, mime_type=f"image/{format}")
        else:
            raise InvalidImageInput(
                message_format=f"Unsupported image resource: {resource}. "
                "Supported Resources are [path, base64, url].",
                target=ErrorTarget.EXECUTOR,
            )


def _create_image_from_dict_v2(image_dict: dict):
    image_type = image_dict["type"]
    if image_type == "image_url":
        if _is_base64(image_dict["image_url"]["url"]):
            return _create_image_from_base64(image_dict["image_url"]["url"])
        elif _is_url(image_dict["image_url"]["url"]):
            return _create_image_from_url(image_dict["image_url"]["url"])
        else:
            raise InvalidImageInput(
                message_format=f"Invalid image url: {image_dict['image_url']}."
                "Should be a valid url or base64 string.",
                target=ErrorTarget.EXECUTOR,
            )
    elif image_type == "image_file":
        return _create_image_from_file(Path(image_dict["image_file"]["path"]))
    else:
        raise InvalidImageInput(
            message_format=f"Unsupported image type: {image_type}. " "Supported types are [image_url, image_file].",
            target=ErrorTarget.EXECUTOR,
        )


def _create_image_from_string(value: str):
    if _is_base64(value):
        return _create_image_from_base64(value)
    elif _is_url(value):
        return _create_image_from_url(value)
    else:
        return _create_image_from_file(Path(value))


def create_image(value: any):
    if isinstance(value, PFBytes):
        return value
    elif isinstance(value, dict):
        if is_multimedia_dict(value):
            return _create_image_from_dict_v1(value)
        elif is_multimedia_dict_v2(value):
            return _create_image_from_dict_v2(value)
        else:
            raise InvalidImageInput(
                message_format="Invalid image input format. The image input should be a dictionary like: "
                "{{data:image/<image_type>;[path|base64|url]: <image_data>}}.",
                target=ErrorTarget.EXECUTOR,
            )
    elif isinstance(value, str):
        if not value:
            raise InvalidImageInput(message_format="The image input should not be empty.", target=ErrorTarget.EXECUTOR)
        return _create_image_from_string(value)
    else:
        raise InvalidImageInput(
            message_format=f"Unsupported image input type: {type(value)}. "
            "The image inputs should be a string or a dictionary.",
            target=ErrorTarget.EXECUTOR,
        )


def create_text_from_dict(text_dict: any):
    return Text.deserialize(text_dict)


def _save_image_to_file(
    image: Image, file_name: str, folder_path: Path, relative_path: Path = None, use_absolute_path=False, version=1
):
    ext = _get_extension_from_mime_type(image._mime_type)
    file_name = f"{file_name}.{ext}" if ext else file_name
    image_path = (relative_path / file_name).as_posix() if relative_path else file_name
    if use_absolute_path:
        image_path = Path(folder_path / image_path).resolve().as_posix()
    if version == 2:
        image_reference = {"type": "image_file", "image_file": {"path": image_path}}
    else:
        image_reference = {f"data:{image._mime_type};path": image_path}
    path = folder_path / relative_path if relative_path else folder_path
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, file_name), "wb") as file:
        file.write(image)
    return image_reference


def get_file_reference_encoder(
    folder_path: Path, relative_path: Path = None, *, use_absolute_path=False, version=1
) -> Callable:
    def pfbytes_file_reference_encoder(obj):
        """Dumps PFBytes to a file and returns its reference."""
        if obj.source_url:
            return {f"data:{obj._mime_type};url": obj.source_url}
        if isinstance(obj, PFBytes):
            if obj.source_url and version == 2:
                return {"type": "image_url", "image_url": {"url": obj.source_url}}
            file_name = str(uuid.uuid4())
            # If use_absolute_path is True, the image file path in image dictionary will be absolute path.
            return _save_image_to_file(obj, file_name, folder_path, relative_path, use_absolute_path, version=version)
        raise TypeError(f"Not supported to dump type '{type(obj).__name__}'.")

    return pfbytes_file_reference_encoder


def default_json_encoder(obj):
    if isinstance(obj, PFBytes):
        return str(obj)
    elif isinstance(obj, Text):
        return str(obj)
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def persist_multimedia_data(value: Any, base_dir: Path, sub_dir: Path = None, version=1):
    pfbytes_file_reference_encoder = get_file_reference_encoder(base_dir, sub_dir, version=version)
    serialization_funcs = {
        Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder}),
        Text: Text.serialize,
    }
    return _process_recursively(value, process_funcs=serialization_funcs)


def convert_multimedia_data_to_base64(value: Any, with_type=False, dict_type=False):
    to_base64_funcs = {PFBytes: partial(PFBytes.to_base64, **{"with_type": with_type, "dict_type": dict_type})}
    return _process_recursively(value, process_funcs=to_base64_funcs)


# TODO: Move this function to a more general place and integrate serialization to this function.
def _process_recursively(value: Any, process_funcs: Dict[type, Callable] = None, inplace: bool = False) -> dict:
    if process_funcs:
        for cls, f in process_funcs.items():
            if isinstance(value, cls):
                return f(value)
    if isinstance(value, list):
        if inplace:
            for i in range(len(value)):
                value[i] = _process_recursively(value[i], process_funcs, inplace)
        else:
            return [_process_recursively(v, process_funcs, inplace) for v in value]
    elif isinstance(value, dict):
        if inplace:
            for k, v in value.items():
                value[k] = _process_recursively(v, process_funcs, inplace)
        else:
            return {k: _process_recursively(v, process_funcs, inplace) for k, v in value.items()}
    return value


def load_multimedia_data(inputs: Dict[str, FlowInputDefinition], line_inputs: dict, version=1):
    updated_inputs = dict(line_inputs or {})
    for key, value in inputs.items():
        try:
            if value.type == ValueType.IMAGE:
                if isinstance(updated_inputs[key], list):
                    # For aggregation node, the image input is a list.
                    updated_inputs[key] = [create_image(item) for item in updated_inputs[key]]
                else:
                    updated_inputs[key] = create_image(updated_inputs[key])
            elif value.type == ValueType.LIST or value.type == ValueType.OBJECT:
                updated_inputs[key] = load_multimedia_data_recursively(updated_inputs[key], version=version)
        except Exception as ex:
            error_type_and_message = f"({ex.__class__.__name__}) {ex}"
            raise LoadMultimediaDataError(
                message_format="Failed to load image for input '{key}': {error_type_and_message}",
                key=key,
                error_type_and_message=error_type_and_message,
                target=ErrorTarget.EXECUTOR,
            ) from ex
    return updated_inputs


def load_multimedia_data_recursively(value: Any, version=1):
    process_funcs = {1: _create_image_from_dict_v1, 2: _create_image_from_dict_v2}
    return _process_multimedia_dict_recursively(
        value, process_funcs[version], create_text_from_dict if version == 2 else None
    )


def resolve_multimedia_data_recursively(input_dir: Path, value: Any):
    process_func = partial(resolve_image_path, **{"input_dir": input_dir})
    return _process_multimedia_dict_recursively(value, process_func)


def _process_multimedia_dict_recursively(
    value: Any, process_func: Callable, text_process_func: Callable = None
) -> dict:
    if isinstance(value, list):
        return [_process_multimedia_dict_recursively(item, process_func, text_process_func) for item in value]
    elif isinstance(value, dict):
        if is_multimedia_dict(value) or is_multimedia_dict_v2(value):
            return process_func(**{"image_dict": value})
        elif text_process_func is not None and is_text_dict(value):
            return text_process_func(**{"text_dict": value})
        else:
            return {
                k: _process_multimedia_dict_recursively(v, process_func, text_process_func) for k, v in value.items()
            }
    else:
        return value


def resolve_image_path(input_dir: Path, image_dict: dict):
    """Resolve image path to absolute path in image dict"""

    input_dir = input_dir.parent if input_dir.is_file() else input_dir
    if is_multimedia_dict(image_dict):
        for key in image_dict:
            _, resource = _get_multimedia_info(key)
            if resource == "path":
                image_dict[key] = str(input_dir / image_dict[key])
    return image_dict
