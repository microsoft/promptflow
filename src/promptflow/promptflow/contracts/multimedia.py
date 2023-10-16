import base64
import hashlib
import os
import re
import requests
import uuid
from pathlib import Path
from typing import Callable

from promptflow.contracts._errors import InvalidImageInput
from promptflow.exceptions import ErrorTarget


class PFBytes(bytes):
    """This class is used to represent a bytes object in PromptFlow.
    It has all the functionalities of a bytes object,
    and also has some additional methods to help with serialization and deserialization.
    """

    MIME_PATTERN = r"^data:image/(.*);(path|base64|url)$"

    def __new__(cls, value: bytes, *args, **kwargs):
        # Here we must only pass the value to the bytes constructor,
        # otherwise we will get a type error that the constructor doesn't take such args.
        # See https://docs.python.org/3/reference/datamodel.html#object.__new__
        return super().__new__(cls, value)

    def __init__(self, data: bytes, mime_type: str):
        super().__init__()
        # Use this hash to identify this bytes.
        self._hash = hashlib.sha1(data).hexdigest()[:8]
        self._mime_type = mime_type

    @staticmethod
    def _get_mime_type_from_path(path: Path):
        ext = path.suffix[1:]
        return f"image/{ext}" if ext else "image/*"

    @staticmethod
    def _get_extension_from_mime_type(mime_type: str):
        ext = mime_type.split("/")[-1]
        if ext == "*":
            return None
        return ext

    @staticmethod
    def is_multimedia_data(image_dict: dict):
        if len(image_dict) != 1:
            return False
        key = list(image_dict.keys())[0]
        if re.match(PFBytes.MIME_PATTERN, key):
            return True
        return False

    @staticmethod
    def get_multimedia_info(key: str):
        match = re.match(PFBytes.MIME_PATTERN, key)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def save_to_file(self, file_name: str, folder_path: Path, relative_path: Path = None):
        ext = PFBytes._get_extension_from_mime_type(self._mime_type)
        file_name = f"{file_name}.{ext}" if ext else file_name
        image_info = {
            f"data:{self._mime_type};path": str(relative_path / file_name) if relative_path else file_name
        }
        path = folder_path / relative_path if relative_path else folder_path
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, file_name), 'wb') as file:
            file.write(self)
        return image_info

    @classmethod
    def get_file_reference_encoder(cls, folder_path: Path, relative_path: Path = None) -> Callable:
        def pfbytes_file_reference_encoder(obj):
            """Dumps PFBytes to a file and returns its reference."""
            if isinstance(obj, PFBytes):
                file_name = str(uuid.uuid4())
                return obj.save_to_file(file_name, folder_path, relative_path)
            raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)
        return pfbytes_file_reference_encoder


class Image(PFBytes):
    def __init__(self, data: bytes, mime_type: str = "image/*"):
        return super().__init__(data, mime_type)

    def __str__(self):
        return f"Image({self._hash})"

    @staticmethod
    def from_file(f: Path, mime_type: str = None):
        if not mime_type:
            mime_type = PFBytes._get_mime_type_from_path(f)
        with open(f, "rb") as fin:
            return Image(fin.read(), mime_type=mime_type)

    @staticmethod
    def from_base64(base64_str: str, mime_type: str):
        image_bytes = base64.b64decode(base64_str)
        return Image(image_bytes, mime_type=mime_type)

    @staticmethod
    def from_url(url: str, mime_type):
        response = requests.get(url)
        if response.status_code == 200:
            return Image(response.content, mime_type=mime_type)
        else:
            raise InvalidImageInput(
                message_format=f"Error while fetching image from url: {url}. "
                "Error code: {response.status_code}, Error message: {response.text}.",
                target=ErrorTarget.EXECUTOR,
            )

    @staticmethod
    def from_dict(image_dict: dict):
        for k, v in image_dict.items():
            format, resource = Image.get_multimedia_info(k)
            if resource == "path":
                return Image.from_file(v, mime_type=f"image/{format}")
            elif resource == "base64":
                return Image.from_base64(v, mime_type=f"image/{format}")
            elif resource == "url":
                return Image.from_url(v, mime_type=f"image/{format}")
            else:
                raise InvalidImageInput(
                    message_format=f"Unsupported image resource: {resource}. "
                    "Supported Resources are [path, base64, url].",
                    target=ErrorTarget.EXECUTOR,
                )

    @staticmethod
    def create(value: any, image_dir: Path = None):
        if isinstance(value, Image):
            return value
        elif isinstance(value, dict):
            if PFBytes.is_multimedia_data(value):
                return Image.from_dict(value)
            else:
                raise InvalidImageInput(
                    message_format="Invalid image input format. The image input should be a dictionary like: "
                    "{data:image/<image_type>;[path|base64|url]:<image_data>}.",
                    target=ErrorTarget.EXECUTOR,
                )
        elif isinstance(value, str):
            image_path = Path(value)
            if not image_path.is_absolute():
                image_path = Path.joinpath(image_dir, image_path)
            return Image.from_file(image_path)
        else:
            raise InvalidImageInput(
                message_format=f"Unsupported image input: {type(value)}. "
                "The image inputs should be a path string or a dictionary.",
                target=ErrorTarget.EXECUTOR,
            )

    def to_base64(self):
        return base64.b64encode(self).decode("utf-8")

    def serialize(self, encoder: Callable = None):
        if encoder is None:
            return self.__str__()
        return encoder(self)


class ChatInputList(list):
    def __str__(self):
        return "\n".join(str(i) for i in self)
