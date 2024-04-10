# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict, Type, Any, Optional
from pathlib import Path

from promptflow._constants import FlowLanguage
from promptflow._proxy._base_executor_proxy import AbstractExecutorProxy
from promptflow._proxy._base_inspector_proxy import AbstractInspectorProxy
from promptflow._proxy._csharp_executor_proxy import CSharpExecutorProxy
from promptflow._proxy._csharp_inspector_proxy import CSharpInspectorProxy
from promptflow._proxy._python_executor_proxy import PythonExecutorProxy
from promptflow._proxy._python_inspector_proxy import PythonInspectorProxy
from promptflow._utils.async_utils import async_run_allowing_running_loop


class ProxyFactory:
    executor_proxy_classes: Dict[str, Type[AbstractExecutorProxy]] = {
        FlowLanguage.Python: PythonExecutorProxy,
        FlowLanguage.CSharp: CSharpExecutorProxy,
    }

    inspector_proxy_classes: Dict[str, Type[AbstractInspectorProxy]] = {
        FlowLanguage.Python: PythonInspectorProxy,
        FlowLanguage.CSharp: CSharpInspectorProxy,
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
        :type executor_proxy_cls:  ~promptflow._proxy.AbstractExecutorProxy
        """
        cls.executor_proxy_classes[language] = executor_proxy_cls

    def create_executor_proxy(
        self,
        flow_file,
        working_dir,
        connections,
        storage,
        language: str,
        init_kwargs: dict = None,
        # below parameters are added for multi-container
        # executor_client is provided by runtime PythonExecutorClient class
        executor_client: Optional[Any] = None,
        environment_variables: Optional[dict] = None,
        log_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        worker_count: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
        **kwargs
    ) -> AbstractExecutorProxy:
        executor_proxy_cls = self.get_executor_proxy_cls(language)
        return async_run_allowing_running_loop(
            executor_proxy_cls.create,
            flow_file,
            working_dir,
            connections=connections,
            storage=storage,
            init_kwargs=init_kwargs,
            executor_client=executor_client,
            environment_variables=environment_variables,
            log_path=log_path,
            output_dir=output_dir,
            worker_count=worker_count,
            line_timeout_sec=line_timeout_sec,
            **kwargs,
        )

    def create_inspector_proxy(self, language: str, **kwargs) -> AbstractInspectorProxy:
        if language not in self.inspector_proxy_classes:
            raise ValueError(f"Unsupported language: {language}")

        inspector_proxy_cls = self.inspector_proxy_classes[language]
        return inspector_proxy_cls()
