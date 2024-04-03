from abc import ABC, abstractmethod


class FileClient(ABC):

    @abstractmethod
    def if_file_exist(self) -> bool:
        pass

    @abstractmethod
    def load(self) -> str:
        pass
