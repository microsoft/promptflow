# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow import load_flow
from promptflow._sdk._constants import DAG_FILE_NAME
from promptflow._sdk._errors import ChatAgentError, ChatIOError
from promptflow._sdk.entities._chat_group._chat_group_io import ChatAgentInputs, ChatAgentOutputs
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import load_yaml

logger = get_cli_sdk_logger()


class ChatAgent:
    """Chat agent entity"""

    def __init__(self, flow: Union[str, PathLike], name: str = None, **kwargs):
        self.flow = self._validate_flow(flow)
        self.name = name or self.flow.name
        self.inputs, self.outputs = self._build_agent_io(flow)
        self._flow_object = load_flow(self.flow)

    def _validate_flow(self, flow: Union[str, PathLike]):
        """Validate flow"""
        logger.debug(f"Validating chat agent flow source {flow!r}")
        flow_path = Path(flow).resolve()
        dag_file = flow_path / DAG_FILE_NAME
        if not dag_file.exists():
            raise ChatAgentError(f"Flow {flow_path.resolve().as_posix()!r} does not contain {DAG_FILE_NAME}.")
        return flow_path

    def _build_agent_io(self, flow: Union[str, PathLike]):
        """Build agent io"""
        logger.debug(f"Building chat agent io for flow {flow!r}")
        flow_dict = load_yaml(Path(flow) / DAG_FILE_NAME)
        inputs = flow_dict.get("inputs", {})
        for key in inputs:
            inputs[key]["referenced_name"] = f"${{{self.name}.inputs.{key}}}"
            # current reference is a in-flow reference, so we need to remove the value
            inputs[key].pop("reference", None)
        outputs = flow_dict.get("outputs", {})
        for key in outputs:
            outputs[key]["referenced_name"] = f"${{{self.name}.outputs.{key}}}"
            # current reference is a in-flow reference, so we need to remove the value
            outputs[key].pop("reference", None)
        return ChatAgentInputs(inputs), ChatAgentOutputs(outputs)

    def _update_input(self, key, value) -> None:
        if not isinstance(value, self.inputs[key]["type"]):
            raise ChatIOError(
                f"Failed to update input {key!r} for agent {self.name!r}, "
                f"expected {self.inputs[key]['type']!r}, got {value!r} with type {type(value)!r}."
            )
        self.inputs[key]["value"] = value

    def set_inputs(self, **kwargs):
        """Set inputs"""
        from promptflow._sdk.entities._chat_group._chat_group import ChatGroupHistory

        for key in self.inputs:
            if key in kwargs:
                value = kwargs[key]
                # if value is a dict, it means it's a reference
                if isinstance(value, dict):
                    self.inputs[key]["reference"] = value["referenced_name"]
                # if it's a string and starts with "${", it's a reference
                elif isinstance(value, str) and value.startswith("${"):
                    self.inputs[key]["reference"] = value
                elif isinstance(value, ChatGroupHistory):
                    self.inputs[key]["value"] = value.history
                else:
                    self._update_input(key, value)

    def invoke(self, **kwargs):
        """Invoke"""
        return self._flow_object(**kwargs)
