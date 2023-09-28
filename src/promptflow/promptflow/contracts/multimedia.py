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

    def __init__(self, data: bytes, mime_type: str, path : str = None):
        super().__init__()
        # Use this hash to identify this bytes.
        self._hash = hashlib.sha1(data).hexdigest()[:8]
        self._mime_type = mime_type
        self._path = path


class Image(PFBytes):
    def __init__(self, data: bytes, mime_type: str = "image/*", path: str = None):
        return super().__init__(data, mime_type, path)

    @staticmethod
    def from_file(f: Path, record_absolute_path: bool = False):
        path = str(f) if record_absolute_path else f.name
        with open(f, "rb") as fin:
            return Image(fin.read(), path=path)

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
        if self._path:
            return {"pf_mime_type": self._mime_type, "path": self._path}
        else:
            return {"pf_mime_type": self._mime_type, "base64": self.to_base64()}

    def save_to(self, name, working_dir: Path = None, relative_path: Path = None):
        file_name = f"{name}.{self.get_extension()}"
        if not working_dir:
            working_dir = Path.cwd()
        if not relative_path:
            self._path = "./" + file_name
        else:
            self._path = str(relative_path / file_name)
        path = working_dir / relative_path if relative_path else working_dir
        if not path.exists():
            path.mkdir(parents=True)
        with open(path / file_name, "wb") as f:
            f.write(self)
