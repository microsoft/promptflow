import base64
import os
import re
import uuid
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict
from urllib.parse import urlparse

import requests

from promptflow._utils._errors import InvalidImageInput, LoadMultimediaDataError
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.multimedia import Image, PFBytes
from promptflow.contracts.tool import ValueType
from promptflow.exceptions import ErrorTarget

MIME_PATTERN = re.compile(r"^data:image/(.*);(path|base64|url)$")


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
    base64_regex = re.compile(r"^([A-Za-z0-9+/]{4})*(([A-Za-z0-9+/]{2})*(==|[A-Za-z0-9+/]=)?)?$")
    if re.match(base64_regex, value):
        return True
    return False


def _create_image_from_file(f: Path, mime_type: str = None):
    with open(f, "rb") as fin:
        return Image(fin.read(), mime_type=mime_type)


def _create_image_from_base64(base64_str: str, mime_type: str = None):
    image_bytes = base64.b64decode(base64_str)
    return Image(image_bytes, mime_type=mime_type)


def _create_image_from_url(url: str, mime_type: str = None):
    response = requests.get(url)
    if response.status_code == 200:
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


def _create_image_from_dict(image_dict: dict):
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
            return _create_image_from_dict(value)
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


def _save_image_to_file(
    image: Image, file_name: str, folder_path: Path, relative_path: Path = None, use_absolute_path=False
):
    ext = _get_extension_from_mime_type(image._mime_type)
    file_name = f"{file_name}.{ext}" if ext else file_name
    image_path = (relative_path / file_name).as_posix() if relative_path else file_name
    if use_absolute_path:
        image_path = Path(folder_path / image_path).resolve().as_posix()
    image_reference = {f"data:{image._mime_type};path": image_path}
    path = folder_path / relative_path if relative_path else folder_path
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, file_name), "wb") as file:
        file.write(image)
    return image_reference


def get_file_reference_encoder(folder_path: Path, relative_path: Path = None, *, use_absolute_path=False) -> Callable:
    def pfbytes_file_reference_encoder(obj):
        """Dumps PFBytes to a file and returns its reference."""
        if obj.source_url:
            return {f"data:{obj._mime_type};url": obj.source_url}
        if isinstance(obj, PFBytes):
            file_name = str(uuid.uuid4())
            # If use_absolute_path is True, the image file path in image dictionary will be absolute path.
            return _save_image_to_file(obj, file_name, folder_path, relative_path, use_absolute_path)
        raise TypeError(f"Not supported to dump type '{type(obj).__name__}'.")

    return pfbytes_file_reference_encoder


def default_json_encoder(obj):
    if isinstance(obj, PFBytes):
        return str(obj)
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def persist_multimedia_data(value: Any, base_dir: Path, sub_dir: Path = None):
    pfbytes_file_reference_encoder = get_file_reference_encoder(base_dir, sub_dir)
    serialization_funcs = {Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder})}
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


def load_multimedia_data(inputs: Dict[str, FlowInputDefinition], line_inputs: dict):
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
                updated_inputs[key] = load_multimedia_data_recursively(updated_inputs[key])
        except Exception as ex:
            error_type_and_message = f"({ex.__class__.__name__}) {ex}"
            raise LoadMultimediaDataError(
                message_format="Failed to load image for input '{key}': {error_type_and_message}",
                key=key,
                error_type_and_message=error_type_and_message,
                target=ErrorTarget.EXECUTOR,
            ) from ex
    return updated_inputs


def load_multimedia_data_recursively(value: Any):
    return _process_multimedia_dict_recursively(value, _create_image_from_dict)


def resolve_multimedia_data_recursively(input_dir: Path, value: Any):
    process_func = partial(resolve_image_path, **{"input_dir": input_dir})
    return _process_multimedia_dict_recursively(value, process_func)


def _process_multimedia_dict_recursively(value: Any, process_func: Callable) -> dict:
    if isinstance(value, list):
        return [_process_multimedia_dict_recursively(item, process_func) for item in value]
    elif isinstance(value, dict):
        if is_multimedia_dict(value):
            return process_func(**{"image_dict": value})
        else:
            return {k: _process_multimedia_dict_recursively(v, process_func) for k, v in value.items()}
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
