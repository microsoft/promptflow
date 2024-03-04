# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow._sdk._constants import DAG_FILE_NAME
from promptflow._sdk._errors import ChatAgentError
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
        inputs = ChatAgentInputs(flow_dict.get("inputs", {}))
        for key in inputs:
            inputs[key]["referenced_name"] = f"${{{self.name}.inputs.{key}}}"
        outputs = ChatAgentOutputs(flow_dict.get("outputs", {}))
        for key in outputs:
            outputs[key]["referenced_name"] = f"${{{self.name}.outputs.{key}}}"
        return inputs, outputs

    def set_inputs(self, **kwargs):
        """Set inputs"""
        # for key in kwargs:
        #     item = kwargs[key]
