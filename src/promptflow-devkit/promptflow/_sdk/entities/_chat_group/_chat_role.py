# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Dict, Optional, Union, Any

from promptflow._sdk._constants import DAG_FILE_NAME
from promptflow._sdk._errors import ChatRoleError
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk.entities._chat_group._chat_group_io import ChatRoleInputs, ChatRoleOutputs
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.flow import Flow
from promptflow._constants import LANGUAGE_KEY, FlowLanguage

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

    def __init__(self,
                 flow: Union[str, PathLike],
                 role: str,
                 inputs: Optional[Dict] = None,
                 name: Optional[str] = None,
                 stop_signal: Optional[str] = None,
                 flow_file: Optional[Path] = None,
                 working_dir: Optional[Path] = None,
                 connections: Optional[Dict[str, Any]] = None,
                 inputs_mapping: Optional[Dict[str, str]] = None,
                 **kwargs):
        self._role = role
        self._flow, self._flow_object = self._validate_flow(flow)
        if inputs is not None:
            self._inputs, self._outputs = self._build_role_io(flow, inputs)

        # Below properties are used for cloud chat group. It may have some duplicate with above ones
        # Will evaluate and refine in the second step.
        if flow_file is not None:
            self._name = name
            self._stop_signal = stop_signal
            self._flow_file = flow_file
            self._working_dir = Flow._resolve_working_dir(flow_file, working_dir)
            self._connections = connections
            self._inputs_mapping = inputs_mapping
            self._flow_definition = Flow.from_yaml(flow_file, working_dir=self._working_dir)

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

    @property
    def name(self):
        """Name of the chat role"""
        return self._name

    @property
    def stop_signal(self):
        """Stop signal of the role"""
        return self._stop_signal

    @property
    def connections(self):
        """Connections of the chat role"""
        return self._connections

    @property
    def working_dir(self):
        """Working directory of the chat role flow"""
        return self._working_dir

    @property
    def inputs_mapping(self):
        """Inputs mapping of the chat role"""
        return self._inputs_mapping

    @property
    def flow_file(self):
        return self._flow_file

    @property
    def flow(self):
        """Flow definition of the chat role"""
        return self._flow_definition

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

    def _update_inputs_from_data_and_inputs(self, data: Dict, inputs: Dict):
        """Update inputs from data and inputs from experiment"""
        data_prefix = "${data."
        inputs_prefix = "${inputs."
        for key in self._inputs:
            current_input = self._inputs[key]
            value = current_input["value"]
            if isinstance(value, str):
                if value.startswith(data_prefix):
                    stripped_value = value.replace(data_prefix, "").replace("}", "")
                    data_name, col_name = stripped_value.split(".")
                    if data_name in data and col_name in data[data_name]:
                        current_input["value"] = data[data_name][col_name]
                elif value.startswith(inputs_prefix):
                    input_name = value.replace(inputs_prefix, "").replace("}", "")
                    if input_name in inputs and input_name in inputs:
                        current_input["value"] = inputs[input_name]

    def invoke(self, *args, **kwargs):
        """Invoke chat role"""
        if args:
            raise ChatRoleError(f"Chat role invoke does not accept positional arguments, got {args!r} instead.")
        result = self._flow_object(**kwargs) or {}
        return result

    def check_language_from_yaml(self):
        flow_file = self.working_dir / self.flow_file if self.working_dir else self.flow_file
        if flow_file.suffix.lower() == ".dll":
            return FlowLanguage.CSharp
        with open(flow_file, "r", encoding="utf-8") as fin:
            flow_dag = load_yaml(fin)
        language = flow_dag.get(LANGUAGE_KEY, FlowLanguage.Python)
        return language
