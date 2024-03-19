from pathlib import Path
from typing import Optional

from promptflow.contracts.tool import InputDefinition
from promptflow.core._flow import Prompty
from promptflow.storage import AbstractRunStorage
from promptflow.tracing._trace import _traced

from ._script_executor import ScriptExecutor


class PromptyExecutor(ScriptExecutor):
    def __init__(
        self,
        flow_file: Path,
        connections: Optional[dict] = None,
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
    ):

        self.prompty = Prompty.load(source=flow_file)
        super().__init__(flow_file=flow_file, connections=connections, working_dir=working_dir, storage=storage)

    def _initialize_function(self):
        # If the function is not decorated with trace, add trace for it.
        func = _traced(self.prompty)
        self._func = self.prompty
        inputs = {
            input_name: InputDefinition(type=[input_value["type"]], default=input_value.get("default", None))
            for input_name, input_value in self.prompty._data.get("inputs", {}).items()
        }
        self._inputs = {k: v.to_flow_input_definition() for k, v in inputs.items()}
        self._is_async = False
        return func
