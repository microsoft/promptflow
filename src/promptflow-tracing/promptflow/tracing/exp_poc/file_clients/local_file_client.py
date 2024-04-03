from .file_client import FileClient


class LocalFileClient(FileClient):
    def __init__(self, file_path):
        self.file_path = file_path

    def if_file_exist(self) -> bool:
        import os
        return os.path.isdir(self.file_path)

    def load(self) -> str:
        with open(self.file_path, 'r') as file:
            return file.read()
