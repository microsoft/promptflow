# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Dict, Optional, Union

from promptflow._sdk._constants import DAG_FILE_NAME
from promptflow._sdk._errors import ChatRoleError
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk.entities._chat_group._chat_group_io import ChatRoleInputs, ChatRoleOutputs
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import load_yaml

logger = get_cli_sdk_logger()


class ChatRole:
    """Chat role entity, used in a chat group to participate in a multi-turn conversation.

    :param flow: Path to the flow file.
    :type flow: Union[str, PathLike]
    :param role: Role of the chat role. e.g. assistant, user, etc.
    :type role: str
    :param name: Name of the chat role. If not provided, it will be the flow folder name.
    :type name: Optional[str]
    :param inputs: Inputs value for the chat role.
    :type inputs: Optional[Dict]
    """

    def __init__(self, flow: Union[str, PathLike], role: str, inputs: Optional[Dict] = None, **kwargs):
        self._role = role
        self._flow, self._flow_object = self._validate_flow(flow)
        self._inputs, self._outputs = self._build_role_io(flow, inputs)
        logger.info(f"Created chat role {self.role!r} with flow {self._flow.as_posix()!r}")

    @property
    def role(self):
        """Role of the chat role"""
        return self._role

    @property
    def inputs(self):
        """Inputs of the chat role"""
        return self._inputs

    @property
    def outputs(self):
        """Outputs of the chat role"""
        return self._outputs

    def _validate_flow(self, flow: Union[str, PathLike]):
        """Validate flow"""
        logger.debug(f"Validating chat role flow source {flow!r}")
        flow_path = Path(flow).resolve()
        try:
            flow_object = load_flow(flow_path)
        except Exception as e:
            raise ChatRoleError(f"Failed to create chat role {self.role!r} due to: {str(e)}.") from e
        return flow_path, flow_object

    def _build_role_io(self, flow: Union[str, PathLike], inputs_value: Dict = None):
        """Build role io"""
        logger.debug(f"Building io for chat role {self.role!r}.")
        flow_dict = load_yaml(Path(flow) / DAG_FILE_NAME)
        inputs = flow_dict.get("inputs", {})
        for key in inputs:
            # fill the inputs with the provided values
            # TODO: Shall we check the value type here or leave it to executor?
            inputs[key]["value"] = inputs_value.get(key, None)
            # current reference is an in-flow reference, not needed here
            inputs[key].pop("reference", None)
        outputs = flow_dict.get("outputs", {})
        for key in outputs:
            # current reference is an in-flow reference, not needed here
            outputs[key].pop("reference", None)

        # check for ignored inputs
        ignored_keys = set(inputs_value.keys()) - set(inputs.keys())
        if ignored_keys:
            logger.warning(
                f"Ignoring inputs {ignored_keys!r} for chat role {self.role!r}, "
                f"expected one of {list(inputs.keys())!r}."
            )

        # check for missing inputs
        missing_keys = []
        for key in inputs:
            if inputs[key].get("value") is None and inputs[key].get("default") is None:
                missing_keys.append(key)
        if missing_keys:
            logger.warning(
                f"Missing inputs {missing_keys!r} for chat role {self.role!r}. These inputs does not have provided "
                f"value or default value."
            )
        return ChatRoleInputs(inputs), ChatRoleOutputs(outputs)

    def invoke(self, *args, **kwargs):
        """Invoke chat role"""
        if args:
            raise ChatRoleError(f"Chat role invoke does not accept positional arguments, got {args!r} instead.")
        result = self._flow_object(**kwargs) or {}
        return result
