import base64
import uuid
import os

from os import PathLike
from typing import Callable, Dict, Union


MIME_TYPE_FILE_EXTENSION_MAP = {
    "image/bmp": "bmp",
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/svg+xml": "svg",
    "image/tiff": "tiff",
}


class PFBytes:
    def __init__(self, mime_type: str, bytes: bytes):
        self.mime_type = mime_type
        self.bytes = bytes

    def save_to_file(self, file_path: PathLike):
        with open(file_path, 'wb') as file:
            file.write(self.bytes)

    @classmethod
    def load_from_file(cls, mime_type: str, file_path: PathLike) -> 'PFBytes':
        with open(file_path, 'rb') as file:
            return cls(mime_type, file.read())

    def save_to_base64(self):
        return base64.b64encode(self.bytes).decode('utf-8')

    @classmethod
    def load_from_base64(cls, mime_type: str, base64_str: str) -> 'PFBytes':
        return cls(mime_type, base64.b64decode(base64_str))

    @classmethod
    def get_file_reference_encoder(cls, folder_path: PathLike) -> Callable:
        def pfbytes_file_reference_encoder(obj):
            """Dumps PFBytes to a file and returns its reference."""
            if isinstance(obj, PFBytes):
                file_name = f"{uuid.uuid4()}"
                if obj.mime_type in MIME_TYPE_FILE_EXTENSION_MAP:
                    file_name += f".{MIME_TYPE_FILE_EXTENSION_MAP[obj.mime_type]}"
                os.makedirs(folder_path, exist_ok=True)
                obj.save_to_file(os.path.join(folder_path, file_name))
                return {"pf_mime_type": obj.mime_type, "path": file_name}
            raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)
        return pfbytes_file_reference_encoder

    @classmethod
    def get_file_reference_decoder(cls, folder_path: str) -> Callable:
        def pfbytes_file_reference_decoder(dct):
            """Loads PFBytes from a file."""
            if "pf_mime_type" in dct and "path" in dct:
                return cls.load_from_file(dct["pf_mime_type"], os.path.join(folder_path, dct["path"]))
            return dct
        return pfbytes_file_reference_decoder


def pfbytes_base64_encoder(obj: object) -> Dict:
    """Encodes PFBytes to base64."""
    if isinstance(obj, PFBytes):
        encoded_bytes = obj.save_to_base64()
        return {"pf_mime_type": obj.mime_type, "base64": encoded_bytes}
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)


def pfbytes_base64_decoder(dct: Dict) -> Union[Dict, PFBytes]:
    """Decodes PFBytes from a base64 string."""
    if "pf_mime_type" in dct and "base64" in dct:
        return PFBytes.load_from_base64(dct["pf_mime_type"], dct["base64"])
    return dct
