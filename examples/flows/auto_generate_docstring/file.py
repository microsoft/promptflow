import os


class File:
    def __init__(self, path: str):
        self.__path = os.path.normpath(os.path.abspath(path))
        self.__dirname = os.path.dirname(self.__path)
        self.__basename = os.path.basename(self.__path).split(".")[0]
        self.__language = os.path.basename(self.__path).split(".")[1]

    def content(self) -> str:
        self.__text = open(self.__path, "r").read()
        return self.__text

    def language(self) -> str:
        return self.__language

    def create_doc_file(self, content: str) -> None:
        path = os.path.join(
            self.__dirname,
            self.__basename + f"_doc.{self.__language}",
        )
        open(path, "w").write(content)
