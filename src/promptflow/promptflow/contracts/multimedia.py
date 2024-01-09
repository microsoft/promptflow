import base64
import filetype
import hashlib
from typing import Callable, Optional


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

    def __init__(self, value: bytes, mime_type: str, source_url: Optional[str] = None):
        # Here the first argument should also be "value", the same as __new__.
        # Otherwise we will get error when initialize the object.
        super().__init__()
        # Use this hash to identify this bytes.
        self._hash = hashlib.sha1(value).hexdigest()[:8]
        self._mime_type = mime_type.lower()
        self._source_url = source_url

    @property
    def source_url(self):
        return self._source_url

    def to_base64(self, with_type: bool = False, dict_type: bool = False):
        """Returns the base64 representation of the PFBytes."""

        if with_type:
            if not dict_type:
                return f"data:{self._mime_type};base64," + base64.b64encode(self).decode("utf-8")
            return {f"data:{self._mime_type};base64": base64.b64encode(self).decode("utf-8")}
        return base64.b64encode(self).decode("utf-8")


class Image(PFBytes):
    """This class is used to represent an image in PromptFlow. It is a subclass of
    ~promptflow.contracts.multimedia.PFBytes.
    """

    def __init__(self, value: bytes, mime_type: str = None, source_url: Optional[str] = None):
        if mime_type is None:
            mime_type = filetype.guess_mime(value)
            if mime_type is None or not mime_type.startswith("image/"):
                mime_type = "image/*"
        return super().__init__(value, mime_type, source_url)

    def __str__(self):
        return f"Image({self._hash})"

    def __repr__(self) -> str:
        return f"Image({self._hash})"

    def serialize(self, encoder: Callable = None):
        """Serialize the image to a dictionary."""

        if encoder is None:
            return self.__str__()
        return encoder(self)
