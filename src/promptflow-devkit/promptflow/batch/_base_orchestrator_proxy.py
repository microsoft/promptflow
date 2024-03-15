from typing import Optional, List, Dict, Mapping, Any
from pathlib import Path
from promptflow.contracts.flow import ChatGroupRole
from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import LineResult

class BaseOrchestratorProxy:
    def __init__(
        self,
        **kwargs
    ):
        self._kwargs = kwargs

    def _create_orchestrator():
        pass
    

    def _orchestrate():
        pass