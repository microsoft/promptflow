import os


class File:
    def __init__(self, path: str):
        self._path = os.path.normpath(os.path.abspath(path))
        self._dirname = os.path.dirname(self._path)
        self._filename = os.path.basename(self._path).split(".")[0]
        self._language = os.path.basename(self._path).split(".")[1]

    @property
    def content(self) -> str:
        if not hasattr(self, "_text"):
            self._text = open(self._path, "r").read()
        return self._text

    @property
    def language(self) -> str:
        return self._language

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def dirname(self) -> str:
        return self._dirname

    @property
    def path(self) -> str:
        return self._path

    def override_origin_file(self, content: str) -> None:
        with open(self.path, "w") as f:
            # self._text = content
            f.write(content)

    def create_new_file(self, content: str) -> None:
        path = os.path.join(
            self.dirname,
            self.filename + f"_doc.{self.language}",
        )
        with open(path, "w") as f:
            f.write(content)