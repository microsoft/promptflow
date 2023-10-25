import base64
import imghdr
import os
import re
import uuid
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict
from urllib.parse import urlparse

import requests

from promptflow.contracts._errors import InvalidImageInput
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.multimedia import Image, PFBytes
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
    if not mime_type:
        mime_type = _get_mime_type_from_path(f)
    with open(f, "rb") as fin:
        return Image(fin.read(), mime_type=mime_type)


def _create_image_from_base64(base64_str: str, mime_type: str = None):
    image_bytes = base64.b64decode(base64_str)
    if not mime_type:
        format = imghdr.what(None, image_bytes)
        mime_type = f"image/{format}" if format else "image/*"
    return Image(image_bytes, mime_type=mime_type)


def _create_image_from_url(url: str, mime_type: str = None):
    response = requests.get(url)
    if response.status_code == 200:
        if not mime_type:
            format = imghdr.what(None, response.content)
            mime_type = f"image/{format}" if format else "image/*"
        return Image(response.content, mime_type=mime_type)
    else:
        raise InvalidImageInput(
            message_format=f"Error while fetching image from URL: {url}. "
            "Error code: {response.status_code}. Error message: {response.text}.",
            target=ErrorTarget.EXECUTOR,
        )


def _create_image_from_dict(image_dict: dict):
    for k, v in image_dict.items():
        format, resource = _get_multimedia_info(k)
        if resource == "path":
            return _create_image_from_file(Path(v), mime_type=f"image/{format}")
        elif resource == "base64":
            return _create_image_from_base64(v, mime_type=f"image/{format}")
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
                "{data:image/<image_type>;[path|base64|url]: <image_data>}.",
                target=ErrorTarget.EXECUTOR,
            )
    elif isinstance(value, str):
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
    image_path = str(relative_path / file_name) if relative_path else file_name
    if use_absolute_path:
        image_path = str(folder_path / image_path)
    image_reference = {f"data:{image._mime_type};path": image_path}
    path = folder_path / relative_path if relative_path else folder_path
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, file_name), "wb") as file:
        file.write(image)
    return image_reference


def get_file_reference_encoder(folder_path: Path, relative_path: Path = None, *, use_absolute_path=False) -> Callable:
    def pfbytes_file_reference_encoder(obj):
        """Dumps PFBytes to a file and returns its reference."""
        if isinstance(obj, PFBytes):
            file_name = str(uuid.uuid4())
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
    return recursive_process(value, process_funcs=serialization_funcs)


def convert_multimedia_data_to_base64(value: Any, with_type=False):
    to_base64_funcs = {PFBytes: partial(PFBytes.to_base64, **{"with_type": with_type})}
    return recursive_process(value, process_funcs=to_base64_funcs)


# TODO: Move this function to a more general place and integrate serialization to this function.
def recursive_process(value: Any, process_funcs: Dict[type, Callable] = None) -> dict:
    if process_funcs:
        for cls, f in process_funcs.items():
            if isinstance(value, cls):
                return f(value)
    if isinstance(value, list):
        return [recursive_process(v, process_funcs) for v in value]
    if isinstance(value, dict):
        return {k: recursive_process(v, process_funcs) for k, v in value.items()}
    return value


def load_multimedia_data(inputs: Dict[str, FlowInputDefinition], line_inputs: dict):
    updated_inputs = dict(line_inputs or {})
    for key, value in inputs.items():
        if value.type == ValueType.IMAGE:
            updated_inputs[key] = create_image(updated_inputs[key])
        elif value.type == ValueType.LIST or value.type == ValueType.OBJECT:
            updated_inputs[key] = load_multimedia_data_recursively(updated_inputs[key])
    return updated_inputs


def load_multimedia_data_recursively(value: Any):
    if isinstance(value, list):
        return [load_multimedia_data_recursively(item) for item in value]
    elif isinstance(value, dict):
        if is_multimedia_dict(value):
            return _create_image_from_dict(value)
        else:
            return {k: load_multimedia_data_recursively(v) for k, v in value.items()}
    else:
        return value


def resolve_multimedia_data_recursively(input_dir: Path, value: Any):
    if isinstance(value, list):
        return [resolve_multimedia_data_recursively(input_dir, item) for item in value]
    elif isinstance(value, dict):
        if is_multimedia_dict(value):
            return resolve_image_path(input_dir, value)
        else:
            return {k: resolve_multimedia_data_recursively(input_dir, v) for k, v in value.items()}
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
