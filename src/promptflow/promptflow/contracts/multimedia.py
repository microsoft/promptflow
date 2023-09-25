import base64


class PFBytes(bytes):
    def __init__(self) -> None:
        super().__init__()


class Image(PFBytes):
    global_index = {}

    def __init__(self, bytes: PFBytes, mime_type: str="image/*"):
        self._hash = hash(bytes)
        self._mime_type = mime_type
        super().__init__()
        self.global_index[str(self)] = self

    @staticmethod
    def from_dict(d):
        if "image" in d:
            with open(d["image"], "rb") as fin:
                return Image(fin.read())

    @staticmethod
    def from_file(f):
        with open(f, "rb") as fin:
            return Image(fin.read())

    def __str__(self):
        return f"Image({self._hash})"

    @staticmethod
    def get_by_hash(h) -> "Image":
        return Image.global_index[h]

    def to_base64(self):
        return base64.b64encode(self).decode("utf-8")

    def to_openai_dict(self):
        return {"image": self.to_base64()}
    
    def save(self, path):
        with open(path, "wb") as fout:
            fout.write(self)

    def get_extension(self):
        ext = self._mime_type.split("/")[1]
        if ext == "*":
            return "png"
        return ext

    def serialize(self):
        return {"mime_type": self._mime_type, "image": self.to_base64()}


class ChatInputList(list):
    def __str__(self):
        return "\n".join(str(i) for i in self)
