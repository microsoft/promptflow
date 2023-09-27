import base64
import hashlib
from pathlib import Path


class PFBytes(bytes):
    """This class is used to represent a bytes object in PromptFlow.
    It has all the functionalities of a bytes object,
    and also has some additional methods to help with serialization and deserialization.
    """

    def __new__(cls, value: bytes, *args, **kwargs):
        # Here we must only pass the value to the bytes constructor,
        # otherwise we will get a type error that the constructor doesn't take such args.
        # See https://docs.python.org/3/reference/datamodel.html#object.__new__
        return super().__new__(cls, value)

    def __init__(self, data: bytes, mime_type):
        super().__init__()
        # Use this hash to identify this bytes.
        self._hash = hashlib.sha1(data).hexdigest()[:8]
        self._mime_type = mime_type


class Image(PFBytes):
    def __init__(self, data: bytes, mime_type: str = "image/*"):
        return super().__init__(data, mime_type)

    @staticmethod
    def from_file(f):
        with open(f, "rb") as fin:
            return Image(fin.read())

    def __str__(self):
        return f"Image({self._hash})"

    def to_base64(self):
        return base64.b64encode(self).decode("utf-8")

    def get_extension(self):
        ext = self._mime_type.split("/")[-1]
        if ext == "*":
            return "png"
        return ext

    def serialize(self):
        name = f"image_{self._hash}"
        return self.save_to(name)

    def save_to(self, name, working_dir=None):
        file_name = f"{name}.{self.get_extension()}"
        if not working_dir:
            working_dir = Path.cwd()
        with open(Path(working_dir) / file_name, "wb") as f:
            f.write(self)
        return {"pf_mime_type": self._mime_type, "path": file_name}
