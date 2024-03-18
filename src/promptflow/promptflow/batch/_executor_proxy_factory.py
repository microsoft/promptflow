# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict, Type

from promptflow._constants import FlowLanguage
from promptflow._utils.async_utils import async_run_allowing_running_loop

from ._base_executor_proxy import AbstractExecutorProxy
from ._csharp_executor_proxy import CSharpExecutorProxy
from ._python_executor_proxy import PythonExecutorProxy


class ExecutorProxyFactory:
    executor_proxy_classes: Dict[str, Type[AbstractExecutorProxy]] = {
        FlowLanguage.Python: PythonExecutorProxy,
        FlowLanguage.CSharp: CSharpExecutorProxy,
    }

    def __init__(self):
        pass

    def get_executor_proxy_cls(self, language: str) -> Type[AbstractExecutorProxy]:
        return self.executor_proxy_classes[language]

    @classmethod
    def register_executor(cls, language: str, executor_proxy_cls: Type[AbstractExecutorProxy]):
        """Register a executor proxy class for a specific program language.

        This method allows users to register a executor proxy class for a particular
        programming language. The executor proxy class will be used when creating an instance
        of the BatchEngine for flows written in the specified language.

        :param language: The flow program language of the executor proxy,
        :type language: str
        :param executor_proxy_cls: The executor proxy class to be registered.
        :type executor_proxy_cls:  ~promptflow.batch.AbstractExecutorProxy
        """
        cls.executor_proxy_classes[language] = executor_proxy_cls

    def create_executor_proxy(
        self, flow_file, working_dir, connections, storage, language: str, **kwargs
    ) -> AbstractExecutorProxy:
        executor_proxy_cls = self.get_executor_proxy_cls(language)
        return async_run_allowing_running_loop(
            executor_proxy_cls.create,
            flow_file,
            working_dir,
            connections=connections,
            storage=storage,
            **kwargs,
        )
