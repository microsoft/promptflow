# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict, Type

from promptflow._constants import FlowLanguage
from promptflow._proxy._base_proxy_factory import BaseProxyFactory
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.batch._csharp_executor_proxy import CSharpExecutorProxy
from promptflow.batch._python_executor_proxy import PythonExecutorProxy
from promptflow.batch._chat_group_orchestrator_proxy import ChatGroupOrchestratorProxy


class ProxyFactory(BaseProxyFactory):
    executor_proxy_classes: Dict[str, Type[AbstractExecutorProxy]] = {
        FlowLanguage.Python: PythonExecutorProxy,
        FlowLanguage.CSharp: CSharpExecutorProxy,
    }

    def __init__(self):
        pass

    def get_executor_proxy_cls(self, language: str) -> Type[AbstractExecutorProxy]:
        return self.executor_proxy_classes[language] if language is not None else ChatGroupOrchestratorProxy