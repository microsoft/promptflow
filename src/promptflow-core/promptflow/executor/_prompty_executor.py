from pathlib import Path
from typing import Any, Dict, Optional, Union

from promptflow._constants import FlowType
from promptflow._utils.logger_utils import logger
from promptflow.contracts.flow import PromptyFlow
from promptflow.contracts.tool import InputDefinition
from promptflow.core._flow import Prompty
from promptflow.storage import AbstractRunStorage
from promptflow.tracing._trace import _traced

from ._script_executor import ScriptExecutor


class PromptyExecutor(ScriptExecutor):
    """
    This class is used to execute prompty with different inputs.
    A callable class will be initialized with a prompty file. This callable class will be called when execute line.
    """

    def __init__(
        self,
        flow_file: Union[Path, Prompty],
        connections: Optional[dict] = None,
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self._init_kwargs = init_kwargs or {}
        logger.debug(f"Init params for prompty executor: {init_kwargs}")

        if isinstance(flow_file, Prompty):
            self.prompty = flow_file
        else:
            self.prompty = Prompty.load(source=flow_file, **self._init_kwargs)
        super().__init__(flow_file=flow_file, connections=connections, working_dir=working_dir, storage=storage)

    _execution_target = FlowType.PROMPTY

    @property
    def has_aggregation_node(self):
        return False

    def _initialize_function(self):
        """
        This function will be called when initializing the executor.
        Used to initialize functions to be executed and support inputs.
        Overwrite the initialize logic, using callable prompty as the function to be executed and prompty inputs
        as executor input.
        """
        # If the function is not decorated with trace, add trace for it.
        self._func = _traced(self.prompty, name=self.prompty._name)
        inputs = {
            input_name: InputDefinition(type=[input_value["type"]], default=input_value.get("default", None))
            for input_name, input_value in self.prompty._data.get("inputs", {}).items()
        }
        self._inputs = {k: v.to_flow_input_definition() for k, v in inputs.items()}
        self._is_async = False
        self._func_name = self._get_func_name(func=self._func)
        return self._func

    def _init_input_sign(self):
        configs, _ = Prompty._parse_prompty(self.prompty.path)
        flow = PromptyFlow.deserialize(configs)
        self._inputs_sign = flow.inputs
        # The init signature only used for flex flow, so we set the _init_sign to empty dict for prompty flow.
        self._init_sign = {}

    def get_inputs_definition(self):
        return self._inputs
