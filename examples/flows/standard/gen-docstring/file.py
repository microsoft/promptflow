import logging
import os
from urllib.parse import urlparse
import requests


class File:
    def __init__(self, source: str):
        self._source = source
        self._is_url = source.startswith("http://") or source.startswith("https://")
        if self._is_url:
            parsed_url = urlparse(source)
            path = parsed_url.path
            self._path = os.path.normpath(os.path.abspath(path))
            self._dirname = os.path.dirname(self._path)
            self._filename = os.path.basename(self._path).split(".")[0]
            self._language = os.path.basename(self._path).split(".")[1]
        else:
            self._path = os.path.normpath(os.path.abspath(source))
            self._dirname = os.path.dirname(self._path)
            self._filename = os.path.basename(self._path).split(".")[0]
            self._language = os.path.basename(self._path).split(".")[1]

    def _read_content(self):
        if self._is_url:
            response = requests.get(self.source)
            if response.status_code == 200:
                content = response.text
                return content
            else:
                print(f"Failed to retrieve content from URL: {self.source}")
                return None
        else:
            try:
                with open(self._path, "r") as file:
                    content = file.read()
                    return content
            except FileNotFoundError:
                print(f"File not found: {self.source}")
                return None

    @property
    def content(self) -> str:
        if not hasattr(self, "_text"):
            self._content = self._read_content()
        return self._content

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
    def source(self) -> str:
        return self._source

    def override_origin_file(self, content: str) -> None:
        if not self._is_url:
            with open(self._path, "w") as f:
                # self._content = content
                f.write(content)
        else:
            logging.warning("Cannot override origin file from URL, create a new file instead.")
            self.create_new_file(content)

    def create_new_file(self, content: str) -> None:
        if self._is_url:
            path = os.path.join(
                './',
                self.filename + f"_doc.{self.language}",
            )
        else:
            path = os.path.join(
                self.dirname,
                self.filename + f"_doc.{self.language}",
            )
        with open(path, "w") as f:
            f.write(content)