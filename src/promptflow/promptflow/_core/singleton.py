from threading import Lock

from promptflow._core._errors import SingletonNotInitializedError
from promptflow.exceptions import ErrorTarget


class Singleton:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise SingletonNotInitializedError(
                message_format="{class_name} instance not yet created.",
                class_name=cls.__name__,
                target=ErrorTarget.EXECUTOR
            )
        return cls._instance
