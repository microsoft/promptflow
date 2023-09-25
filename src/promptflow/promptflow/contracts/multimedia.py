import base64


class PFBytes(bytes):
    def __init__(self) -> None:
        super().__init__()


class Image(PFBytes):
    def __init__(self, bytes: PFBytes, mime_type: str = "image/*"):
        self._hash = hash(bytes)
        self._mime_type = mime_type
        super().__init__()

    @staticmethod
    def from_file(f):
        with open(f, "rb") as fin:
            return Image(fin.read())

    def __str__(self):
        return f"Image({self._hash})"

    def to_base64(self):
        return base64.b64encode(self).decode("utf-8")

    def save(self, path):
        with open(path, "wb") as fout:
            fout.write(self)

    def get_extension(self):
        ext = self._mime_type.split("/")[1]
        if ext == "*":
            return "png"
        return ext

    def serialize(self):
        return {"pf_mime_type": self._mime_type, "base64": self.to_base64()}
