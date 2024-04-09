import base64
import os
import re
import uuid
from abc import ABC, abstractmethod, abstractstaticmethod
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union
from urllib.parse import urlparse

import requests

from promptflow._constants import MessageFormatType
from promptflow._utils._errors import InvalidImageInput, InvalidMessageFormatType, LoadMultimediaDataError
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.multimedia import Image, PFBytes, Text
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.tool import ValueType
from promptflow.exceptions import ErrorTarget


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


MIME_PATTERN = re.compile(r"^data:image/(.*);(path|base64|url)$")


class ImageProcessor:
    @staticmethod
    def get_extension_from_mime_type(mime_type: str):
        ext = mime_type.split("/")[-1]
        if ext == "*":
            return None
        return ext

    @staticmethod
    def get_multimedia_info(key: str):
        match = re.match(MIME_PATTERN, key)
        if match:
            return match.group(1), match.group(2)
        return None, None

    @staticmethod
    def is_url(value: str):
        try:
            result = urlparse(value)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    @staticmethod
    def is_base64(value: str):
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

    @staticmethod
    def create_image_from_file(f: Path, mime_type: str = None):
        with open(f, "rb") as fin:
            return Image(fin.read(), mime_type=mime_type)

    @staticmethod
    def create_image_from_base64(base64_str: str, mime_type: str = None):
        base64_str = base64_str.split(",")[-1]
        image_bytes = base64.b64decode(base64_str)
        return Image(image_bytes, mime_type=mime_type)

    @staticmethod
    def create_image_from_url(url: str, mime_type: str = None):
        response = requests.get(url)
        if response.status_code == 200:
            return Image(response.content, mime_type=mime_type, source_url=url)
        else:
            raise InvalidImageInput(
                message_format=(
                    "Failed to fetch image from URL: {url}. Error code: {error_code}. "
                    "Error message: {error_message}."
                ),
                target=ErrorTarget.EXECUTOR,
                url=url,
                error_code=response.status_code,
                error_message=response.text,
            )

    @staticmethod
    def create_image_from_string(value: str):
        if ImageProcessor.is_base64(value):
            return ImageProcessor.create_image_from_base64(value)
        elif ImageProcessor.is_url(value):
            return ImageProcessor.create_image_from_url(value)
        else:
            return ImageProcessor.create_image_from_file(Path(value))


class TextProcessor:
    @staticmethod
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

    @staticmethod
    def create_text_from_dict(text_dict: any):
        return Text.deserialize(text_dict)


class MultimediaProcessor(ABC):
    @staticmethod
    def create(message_format_type: str = MessageFormatType.BASIC):
        if not message_format_type or message_format_type.lower() == MessageFormatType.BASIC:
            return BasicMultimediaProcessor()
        if message_format_type.lower() == MessageFormatType.OPENAI_VISION:
            return OpenaiVisionMultimediaProcessor()
        raise InvalidMessageFormatType(
            message_format=(
                f"Invalid message format '{message_format_type}'. "
                "Supported message formats are ['basic', 'openai-vision']."
            ),
        )

    @staticmethod
    def create_from_yaml(flow_file: Path, working_dir: Optional[Path] = None):
        if flow_file and Path(flow_file).suffix.lower() in [".yaml", ".yml"]:
            flow_file = working_dir / flow_file if working_dir else flow_file
            with open(flow_file, "r", encoding="utf-8") as fin:
                flow_dag = load_yaml(fin)
            message_format_type = flow_dag.get("message_format", MessageFormatType.BASIC)
            return MultimediaProcessor.create(message_format_type)
        return BasicMultimediaProcessor()

    def create_image(self, value: any):
        if isinstance(value, PFBytes):
            return value
        elif isinstance(value, dict):
            if self.is_multimedia_dict(value):
                return self._create_image_from_dict(value)
            else:
                raise InvalidImageInput(
                    message_format=(
                        "Invalid image input format. The image input should be a dictionary like: "
                        "{{data:image/<image_type>;[path|base64|url]: <image_data>}}."
                    ),
                    target=ErrorTarget.EXECUTOR,
                )
        elif isinstance(value, str):
            if not value:
                raise InvalidImageInput(
                    message_format="The image input should not be empty.", target=ErrorTarget.EXECUTOR
                )
            return ImageProcessor.create_image_from_string(value)
        else:
            raise InvalidImageInput(
                message_format=(
                    f"Unsupported image input type: {type(value)}. "
                    "The image inputs should be a string or a dictionary."
                ),
                target=ErrorTarget.EXECUTOR,
            )

    def _save_image_to_file(
        self, image: Image, file_name: str, folder_path: Path, relative_path: Path = None, use_absolute_path=False
    ):
        ext = ImageProcessor.get_extension_from_mime_type(image._mime_type)
        file_name = f"{file_name}.{ext}" if ext else file_name
        image_path = (relative_path / file_name).as_posix() if relative_path else file_name
        if use_absolute_path:
            image_path = Path(folder_path / image_path).resolve().as_posix()
        image_reference = self._generate_image_file_reference(image, image_path)
        path = folder_path / relative_path if relative_path else folder_path
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, file_name), "wb") as file:
            file.write(image)
        return image_reference

    def get_file_reference_encoder(
        self, folder_path: Path, relative_path: Path = None, use_absolute_path=False
    ) -> Callable:
        def pfbytes_file_reference_encoder(obj):
            """Dumps PFBytes to a file and returns its reference."""
            if obj.source_url:
                return self._generate_image_url_reference(obj)
            if isinstance(obj, PFBytes):
                file_name = str(uuid.uuid4())
                # If use_absolute_path is True, the image file path in image dictionary will be absolute path.
                return self._save_image_to_file(obj, file_name, folder_path, relative_path, use_absolute_path)
            raise TypeError(f"Not supported to dump type '{type(obj).__name__}'.")

        return pfbytes_file_reference_encoder

    def load_multimedia_data(self, inputs: Dict[str, FlowInputDefinition], line_inputs: dict):
        updated_inputs = dict(line_inputs or {})
        for key, value in inputs.items():
            try:
                if value.type == ValueType.IMAGE:
                    if isinstance(updated_inputs[key], list):
                        # For aggregation node, the image input is a list.
                        updated_inputs[key] = [self.create_image(item) for item in updated_inputs[key]]
                    else:
                        updated_inputs[key] = self.create_image(updated_inputs[key])
                elif value.type == ValueType.LIST or value.type == ValueType.OBJECT:
                    updated_inputs[key] = self.load_multimedia_data_recursively(updated_inputs[key])
            except Exception as ex:
                error_type_and_message = f"({ex.__class__.__name__}) {ex}"
                raise LoadMultimediaDataError(
                    message_format="Failed to load image for input '{key}': {error_type_and_message}",
                    key=key,
                    error_type_and_message=error_type_and_message,
                    target=ErrorTarget.EXECUTOR,
                ) from ex
        return updated_inputs

    @staticmethod
    def _process_multimedia_dict_recursively(value: Any, process_funcs: Dict[Callable[[dict], bool], Callable]) -> dict:
        if isinstance(value, list):
            return [MultimediaProcessor._process_multimedia_dict_recursively(item, process_funcs) for item in value]
        elif isinstance(value, dict):
            for check_func, process_func in process_funcs.items():
                if check_func(value):
                    return process_func(value)
            return {
                k: MultimediaProcessor._process_multimedia_dict_recursively(v, process_funcs) for k, v in value.items()
            }
        else:
            return value

    @staticmethod
    def convert_multimedia_data_to_string(value: Any, inplace=False):
        serialization_funcs = {Image: partial(Image.serialize, **{"encoder": None})}
        return _process_recursively(value, process_funcs=serialization_funcs, inplace=inplace)

    def process_multimedia_in_run_info(
        self, run_info: Union[FlowRunInfo, NodeRunInfo], base_dir: Path, sub_dir: Path = None, use_absolute_path=False
    ):
        """Persist multimedia data in run info to file and update the run info with the file path.
        If sub_dir is not None, the multimedia file path will be sub_dir/file_name, otherwise file_name.
        If use_absolute_path is True, the multimedia file path will be absolute path.
        """
        if run_info.inputs:
            run_info.inputs = self.persist_multimedia_data(run_info.inputs, base_dir, sub_dir, use_absolute_path)
        if run_info.output:
            run_info.output = self.persist_multimedia_data(run_info.output, base_dir, sub_dir, use_absolute_path)
            run_info.result = None
        if run_info.api_calls:
            run_info.api_calls = self.persist_multimedia_data(run_info.api_calls, base_dir, sub_dir, use_absolute_path)

    @abstractstaticmethod
    def is_multimedia_dict(multimedia_dict: dict):
        pass

    @abstractstaticmethod
    def _create_image_from_dict(image_dict: dict):
        pass

    @abstractmethod
    def load_multimedia_data_recursively(self, value: Any):
        pass

    @abstractstaticmethod
    def _generate_image_file_reference(image: PFBytes, image_path: str):
        pass

    @abstractstaticmethod
    def _generate_image_url_reference(image: PFBytes):
        pass

    @abstractmethod
    def resolve_multimedia_data_recursively(self, input_dir: Path, value: Any):
        pass

    @abstractmethod
    def persist_multimedia_data(
        self, value: Any, base_dir: Path, sub_dir: Path = None, use_absolute_path=False, inplace: bool = False
    ):
        pass

    @abstractstaticmethod
    def convert_multimedia_data_to_base64_dict(value: Any):
        pass


class BasicMultimediaProcessor(MultimediaProcessor):
    @staticmethod
    def is_multimedia_dict(multimedia_dict: dict):
        if len(multimedia_dict) != 1:
            return False
        key = list(multimedia_dict.keys())[0]
        if re.match(MIME_PATTERN, key):
            return True
        return False

    @staticmethod
    def _create_image_from_dict(image_dict: dict):
        for k, v in image_dict.items():
            format, resource = ImageProcessor.get_multimedia_info(k)
            if resource == "path":
                return ImageProcessor.create_image_from_file(Path(v), mime_type=f"image/{format}")
            elif resource == "base64":
                if ImageProcessor.is_base64(v):
                    return ImageProcessor.create_image_from_base64(v, mime_type=f"image/{format}")
                else:
                    raise InvalidImageInput(
                        message_format=f"Invalid base64 image: {v}.",
                        target=ErrorTarget.EXECUTOR,
                    )
            elif resource == "url":
                return ImageProcessor.create_image_from_url(v, mime_type=f"image/{format}")
            else:
                raise InvalidImageInput(
                    message_format=(
                        f"Unsupported image resource: {resource}. Supported Resources are [path, base64, url]."
                    ),
                    target=ErrorTarget.EXECUTOR,
                )

    def load_multimedia_data_recursively(self, value: Any):
        process_funcs = {self.is_multimedia_dict: self._create_image_from_dict}
        return self._process_multimedia_dict_recursively(value, process_funcs)

    @staticmethod
    def _generate_image_file_reference(obj: PFBytes, image_path: str):
        return {f"data:{obj._mime_type};path": image_path}

    @staticmethod
    def _generate_image_url_reference(obj: PFBytes):
        return {f"data:{obj._mime_type};url": obj.source_url}

    def _resolve_image_path(self, input_dir: Path, image_dict: dict):
        """Resolve image path to absolute path in image dict"""

        input_dir = input_dir.parent if input_dir.is_file() else input_dir
        if self.is_multimedia_dict(image_dict):
            for key in image_dict:
                _, resource = ImageProcessor.get_multimedia_info(key)
                if resource == "path":
                    image_dict[key] = str(input_dir / image_dict[key])
        return image_dict

    def resolve_multimedia_data_recursively(self, input_dir: Path, value: Any):
        process_funcs = {self.is_multimedia_dict: partial(self._resolve_image_path, input_dir)}
        return self._process_multimedia_dict_recursively(value, process_funcs)

    def persist_multimedia_data(
        self, value: Any, base_dir: Path, sub_dir: Path = None, use_absolute_path=False, inplace: bool = False
    ):
        pfbytes_file_reference_encoder = (
            self.get_file_reference_encoder(base_dir, sub_dir, use_absolute_path=use_absolute_path)
            if base_dir
            else None
        )
        serialization_funcs = {Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder})}
        return _process_recursively(value, process_funcs=serialization_funcs, inplace=inplace)

    @staticmethod
    def convert_multimedia_data_to_base64_dict(value: Any):
        def convert_pfbytes_to_base64_dict(obj: PFBytes):
            return {f"data:{obj._mime_type};base64": obj.to_base64()}

        to_base64_funcs = {PFBytes: convert_pfbytes_to_base64_dict}
        return _process_recursively(value, process_funcs=to_base64_funcs)


class OpenaiVisionMultimediaProcessor(MultimediaProcessor):
    @staticmethod
    def is_multimedia_dict(multimedia_dict: dict):
        if len(multimedia_dict) != 2:
            return False
        if "type" not in multimedia_dict:
            return False
        image_type = multimedia_dict["type"]
        if image_type not in multimedia_dict or not isinstance(multimedia_dict[image_type], dict):
            return False
        if image_type == "image_url" and "url" in multimedia_dict[image_type]:
            return True
        if image_type == "image_file" and "path" in multimedia_dict[image_type]:
            return True
        return False

    @staticmethod
    def _create_image_from_dict(image_dict: dict):
        image_type = image_dict["type"]
        if image_type == "image_url":
            image_url = image_dict["image_url"]["url"]
            if ImageProcessor.is_base64(image_url):
                return ImageProcessor.create_image_from_base64(image_url)
            elif ImageProcessor.is_url(image_url):
                return ImageProcessor.create_image_from_url(image_url)
            else:
                raise InvalidImageInput(
                    message_format=f"Invalid image url: {image_url}. Should be a valid url or base64 string.",
                    target=ErrorTarget.EXECUTOR,
                )
        elif image_type == "image_file":
            return ImageProcessor.create_image_from_file(Path(image_dict["image_file"]["path"]))
        else:
            raise InvalidImageInput(
                message_format=f"Unsupported image type: {image_type}. Supported types are [image_url, image_file].",
                target=ErrorTarget.EXECUTOR,
            )

    def load_multimedia_data_recursively(self, value: Any):
        process_funcs = {
            self.is_multimedia_dict: self._create_image_from_dict,
            TextProcessor.is_text_dict: TextProcessor.create_text_from_dict,
        }
        return self._process_multimedia_dict_recursively(value, process_funcs)

    @staticmethod
    def _generate_image_file_reference(obj: PFBytes, image_path: str):
        return {"type": "image_file", "image_file": {"path": image_path}}

    @staticmethod
    def _generate_image_url_reference(obj: PFBytes):
        return {"type": "image_url", "image_url": {"url": obj.source_url}}

    def _resolve_image_path(self, input_dir: Path, image_dict: dict):
        """Resolve image path to absolute path in image dict"""

        input_dir = input_dir.parent if input_dir.is_file() else input_dir
        if self.is_multimedia_dict(image_dict):
            image_type = image_dict["type"]
            if image_type == "image_file" and "path" in image_dict["image_file"]:
                image_dict["image_file"]["path"] = str(input_dir / image_dict["image_file"]["path"])
        return image_dict

    def resolve_multimedia_data_recursively(self, input_dir: Path, value: Any):
        process_funcs = {self.is_multimedia_dict: partial(self._resolve_image_path, input_dir)}
        return self._process_multimedia_dict_recursively(value, process_funcs)

    def persist_multimedia_data(
        self, value: Any, base_dir: Path, sub_dir: Path = None, use_absolute_path=False, inplace: bool = False
    ):
        pfbytes_file_reference_encoder = (
            self.get_file_reference_encoder(base_dir, sub_dir, use_absolute_path=use_absolute_path)
            if base_dir
            else None
        )
        serialization_funcs = {
            Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder}),
            Text: Text.serialize,
        }
        return _process_recursively(value, process_funcs=serialization_funcs, inplace=inplace)

    @staticmethod
    def convert_multimedia_data_to_base64_dict(value: Any):
        def convert_pfbytes_to_base64_dict(obj: PFBytes):
            return {"type": "image_url", "image_url": {"url": obj.to_base64(with_type=True)}}

        to_base64_funcs = {PFBytes: convert_pfbytes_to_base64_dict}
        return _process_recursively(value, process_funcs=to_base64_funcs)


# TODO：Runtime relies on these old interfaces and will be removed in the future.
def persist_multimedia_data(
    value: Any,
    base_dir: Path,
    sub_dir: Path = None,
    use_absolute_path=False,
    multimedia_processor: MultimediaProcessor = None,
):
    if multimedia_processor:
        return multimedia_processor.persist_multimedia_data(
            value, base_dir, sub_dir, use_absolute_path=use_absolute_path
        )
    return BasicMultimediaProcessor().persist_multimedia_data(
        value, base_dir, sub_dir, use_absolute_path=use_absolute_path
    )


def load_multimedia_data_recursively(value: Any, multimedia_processor: MultimediaProcessor = None):
    if multimedia_processor:
        return multimedia_processor.load_multimedia_data_recursively(value)
    return BasicMultimediaProcessor().load_multimedia_data_recursively(value)


def resolve_multimedia_data_recursively(input_dir: Path, value: Any, multimedia_processor: MultimediaProcessor = None):
    if multimedia_processor:
        return multimedia_processor.resolve_multimedia_data_recursively(input_dir, value)
    return BasicMultimediaProcessor().resolve_multimedia_data_recursively(input_dir, value)
