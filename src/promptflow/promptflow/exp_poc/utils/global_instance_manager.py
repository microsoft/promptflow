import threading
from typing import Dict, Any
from abc import abstractmethod


class SingletonMeta(type):
    def __init__(cls, name, bases, attrs):
        cls._instance = None
        cls._singletonmeta_lock = threading.Lock()
        super().__init__(name, bases, attrs)

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._singletonmeta_lock:
                if cls._instance is None:
                    cls._instance = super().__call__(*args, **kwargs)
        return cls._instance


class GlobalInstanceManager(metaclass=SingletonMeta):

    __instances: Dict[Any, Any] = {}
    __lock = threading.Lock()

    @abstractmethod
    def get_instance(self, **kwargs) -> Any:
        pass

    @abstractmethod
    def _create_instance(self, **kwargs) -> Any:
        pass

    def _get_instance(
        self,
        identifier: Any,
        **kwargs
    ) -> Any:
        if identifier in self.__instances:
            return self.__instances[identifier]
        with self.__lock:
            if identifier in self.__instances:
                return self.__instances[identifier]

            instance = self._create_instance(**kwargs)

            self.__instances[identifier] = instance
            return instance
