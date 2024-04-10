# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

from promptflow._constants import CONNECTION_DATA_CLASS_KEY, CONNECTION_NAME_PROPERTY

from .multimedia import Image
from .types import AssistantDefinition, FilePath, PromptTemplate, Secret

logger = logging.getLogger(__name__)
T = TypeVar("T", bound="Enum")


def _deserialize_enum(cls: Type[T], val) -> T:
    if not all(isinstance(i.value, str) for i in cls):
        return val
    typ = next((i for i in cls if val.lower() == i.value.lower()), None)
    # Keep string value for unknown type, as they may be resolved later after some requisites imported.
    # Type resolve will be ensured in 'ensure_node_inputs_type' before execution.
    return typ if typ else val


class ValueType(str, Enum):
    """Value types."""

    INT = "int"
    DOUBLE = "double"
    BOOL = "bool"
    STRING = "string"
    SECRET = "secret"
    PROMPT_TEMPLATE = "prompt_template"
    LIST = "list"
    OBJECT = "object"
    FILE_PATH = "file_path"
    IMAGE = "image"
    ASSISTANT_DEFINITION = "assistant_definition"

    @staticmethod
    def from_value(t: Any) -> "ValueType":
        """Get :class:`~promptflow.contracts.tool.ValueType` by value.

        :param t: The value needs to get its :class:`~promptflow.contracts.tool.ValueType`
        :type t: Any
        :return: The :class:`~promptflow.contracts.tool.ValueType` of the given value
        :rtype: ~promptflow.contracts.tool.ValueType
        """

        if isinstance(t, Secret):
            return ValueType.SECRET
        if isinstance(t, PromptTemplate):
            return ValueType.PROMPT_TEMPLATE
        if isinstance(t, bool):
            return ValueType.BOOL
        if isinstance(t, int):
            return ValueType.INT
        if isinstance(t, float):
            return ValueType.DOUBLE
        # FilePath is a subclass of str, so it must be checked before str
        if isinstance(t, FilePath):
            return ValueType.FILE_PATH
        if isinstance(t, str):
            return ValueType.STRING
        if isinstance(t, list):
            return ValueType.LIST
        if isinstance(t, AssistantDefinition):
            return ValueType.ASSISTANT_DEFINITION
        return ValueType.OBJECT

    @staticmethod
    def from_type(t: type) -> "ValueType":
        """Get :class:`~promptflow.contracts.tool.ValueType` by type.

        :param t: The type needs to get its :class:`~promptflow.contracts.tool.ValueType`
        :type t: type
        :return: The :class:`~promptflow.contracts.tool.ValueType` of the given type
        :rtype: ~promptflow.contracts.tool.ValueType
        """

        if t == int:
            return ValueType.INT
        if t == float:
            return ValueType.DOUBLE
        if t == bool:
            return ValueType.BOOL
        if t == str:
            return ValueType.STRING
        if t == list:
            return ValueType.LIST
        if t == Secret:
            return ValueType.SECRET
        if t == PromptTemplate:
            return ValueType.PROMPT_TEMPLATE
        if t == FilePath:
            return ValueType.FILE_PATH
        if t == Image:
            return ValueType.IMAGE
        if t == AssistantDefinition:
            return ValueType.ASSISTANT_DEFINITION
        return ValueType.OBJECT

    def parse(self, v: Any) -> Any:  # noqa: C901
        """Parse value to the given :class:`~promptflow.contracts.tool.ValueType`.

        :param v: The value needs to be parsed to the given :class:`~promptflow.contracts.tool.ValueType`
        :type v: Any
        :return: The parsed value
        :rtype: Any
        """

        if self == ValueType.INT:
            return int(v)
        if self == ValueType.DOUBLE:
            return float(v)
        if self == ValueType.BOOL:
            if isinstance(v, bool):
                return v
            if isinstance(v, str) and v.lower() in {"true", "false"}:
                return v.lower() == "true"
            raise ValueError(f"Invalid boolean value {v!r}")
        if self == ValueType.STRING:
            return str(v)
        if self == ValueType.LIST:
            if isinstance(v, str):
                v = json.loads(v)
            if not isinstance(v, list):
                raise ValueError(f"Invalid list value {v!r}")
            return v
        if self == ValueType.OBJECT:
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except Exception:
                    #  Ignore the exception since it might really be a string
                    pass
        # TODO: parse other types
        return v


class ConnectionType:
    """This class provides methods to interact with connection types."""

    @staticmethod
    def get_connection_class(type_name: str) -> Optional[type]:
        """Get connection type by type name.

        :param type_name: The type name of the connection
        :type type_name: str
        :return: The connection type
        :rtype: type
        """

        # Note: This function must be called after ensure_flow_valid, as required modules may not be imported yet,
        # and connections may not be registered yet.
        from promptflow._core.tools_manager import connections

        if not isinstance(type_name, str):
            return None
        return connections.get(type_name)

    @staticmethod
    def is_connection_class_name(type_name: str) -> bool:
        """Check if the given type name is a connection type.

        :param type_name: The type name of the connection
        :type type_name: str
        :return: Whether the given type name is a connection type
        :rtype: bool
        """

        return ConnectionType.get_connection_class(type_name) is not None

    @staticmethod
    def is_connection_value(val: Any) -> bool:
        """Check if the given value is a connection.

        :param val: The value to check
        :type val: Any
        :return: Whether the given value is a connection
        :rtype: bool
        """

        # Note: This function must be called after ensure_flow_valid, as required modules may not be imported yet,
        # and connections may not be registered yet.
        from promptflow._core.tools_manager import connections

        val = type(val) if not isinstance(val, type) else val
        if hasattr(val, CONNECTION_DATA_CLASS_KEY):
            # Get the data class for sdk connection object
            data_class = getattr(val, CONNECTION_DATA_CLASS_KEY)
            logger.debug(f"val {val} has DATA_CLASS key, get the data plane class {data_class}.")
            val = data_class
        return val in connections.values() or ConnectionType.is_custom_strong_type(val)

    @staticmethod
    def is_custom_strong_type(val: Any) -> bool:
        """Check if the given value is a custom strong type connection.

        :param val: The value to check
        :type val: Any
        :return: Whether the given value is a custom strong type
        :rtype: bool
        """

        from promptflow.connections import CustomStrongTypeConnection

        val = type(val) if not isinstance(val, type) else val

        try:
            return issubclass(val, CustomStrongTypeConnection)
        except TypeError as e:
            # TypeError is not expected to happen, but if it does, we will log it for debugging and return False.
            # The try-except block cannot be confidently removed due to the uncertainty of TypeError that may occur.
            logger.warning(f"Failed to check if {val} is a custom strong type: {e}")
            return False

    @staticmethod
    def serialize_conn(connection: Any) -> dict:
        """Serialize the given connection.

        :param connection: The connection to serialize
        :type connection: Any
        :return: A dictionary representation of the connection.
        :rtype: dict
        """

        if not ConnectionType.is_connection_value(connection):
            raise ValueError(f"Invalid connection value {connection!r}")
        return getattr(connection, CONNECTION_NAME_PROPERTY, type(connection).__name__)


class ToolType(str, Enum):
    """Tool types."""

    LLM = "llm"
    PYTHON = "python"
    CSHARP = "csharp"
    PROMPT = "prompt"
    _ACTION = "action"
    CUSTOM_LLM = "custom_llm"


@dataclass
class InputDefinition:
    """Input definition."""

    type: List[ValueType]
    default: str = None
    description: str = None
    enum: List[str] = None
    # Param 'custom_type' is currently used for inputs of custom strong type connection.
    # For a custom strong type connection input, the type should be 'CustomConnection',
    # while the custom_type should be the custom strong type connection class name.
    custom_type: List[str] = None

    def serialize(self) -> dict:
        """Serialize input definition to dict.

        :return: The serialized input definition
        :rtype: dict
        """

        data = {}
        data["type"] = [t.value for t in self.type]
        if len(self.type) == 1:
            data["type"] = self.type[0].value
        if self.default:
            data["default"] = str(self.default)
        if self.description:
            data["description"] = self.description
        if self.enum:
            data["enum"] = self.enum
        if self.custom_type:
            data["custom_type"] = self.custom_type
        return data

    @staticmethod
    def deserialize(data: dict) -> "InputDefinition":
        """Deserialize dict to input definition.

        :param data: The dict needs to be deserialized
        :type data: dict
        :return: The deserialized input definition
        :rtype: ~promptflow.contracts.tool.InputDefinition
        """

        def _deserialize_type(v):
            v = [v] if not isinstance(v, list) else v
            # Note: Connection type will be keep as string value,
            # as they may be resolved later after some requisites imported.
            return [_deserialize_enum(ValueType, item) for item in v]

        return InputDefinition(
            _deserialize_type(data["type"]),
            data.get("default", ""),
            data.get("description", ""),
            data.get("enum", []),
            data.get("custom_type", []),
        )

    def to_flow_input_definition(self):
        """Used for eager flow to convert input definition to flow input definition."""
        from .flow import FlowInputDefinition

        # TODO: To align with tool resolver we respect the first type if multiple types are provided,
        # still need more discussion on this. Should we raise error if multiple types are provided?
        return FlowInputDefinition(
            type=self.type[0], default=self.default, description=self.description, enum=self.enum
        )


@dataclass
class OutputDefinition:
    """Output definition."""

    type: List["ValueType"]
    description: str = ""
    is_property: bool = False

    def serialize(self) -> dict:
        """Serialize output definition to dict.

        :return: The serialized output definition
        :rtype: dict
        """

        data = {"type": [t.value for t in self.type], "is_property": self.is_property}
        if len(data["type"]) == 1:
            data["type"] = data["type"][0]
        if self.description:
            data["description"] = self.description
        return data

    @staticmethod
    def deserialize(data: dict) -> "OutputDefinition":
        """Deserialize dict to output definition.

        :param data: The dict needs to be deserialized
        :type data: dict
        :return: The deserialized output definition
        :rtype: ~promptflow.contracts.tool.OutputDefinition
        """

        return OutputDefinition(
            [ValueType(t) for t in data["type"]] if isinstance(data["type"], list) else [ValueType(data["type"])],
            data.get("description", ""),
            data.get("is_property", False),
        )


@dataclass
class Tool:
    """Tool definition.

    :param name: The name of the tool
    :type name: str
    :param type: The type of the tool
    :type type: ~promptflow.contracts.tool.ToolType
    :param inputs: The inputs of the tool
    :type inputs: Dict[str, ~promptflow.contracts.tool.InputDefinition]
    :param outputs: The outputs of the tool
    :type outputs: Optional[Dict[str, ~promptflow.contracts.tool.OutputDefinition]]
    :param description: The description of the tool
    :type description: Optional[str]
    :param module: The module of the tool
    :type module: Optional[str]
    :param class_name: The class name of the tool
    :type class_name: Optional[str]
    :param source: The source of the tool
    :type source: Optional[str]
    :param code: The code of the tool
    :type code: Optional[str]
    :param function: The function of the tool
    :type function: Optional[str]
    :param connection_type: The connection type of the tool
    :type connection_type: Optional[List[str]]
    :param is_builtin: Whether the tool is a built-in tool
    :type is_builtin: Optional[bool]
    :param stage: The stage of the tool
    :type stage: Optional[str]
    :param enable_kwargs: Whether to enable kwargs, only available for customer python tool
    :type enable_kwargs: Optional[bool]
    :param deprecated_tools: A list of old tool IDs that are mapped to the current tool ID.
    :type deprecated_tools: Optional[List[str]]
    """

    name: str
    type: ToolType
    inputs: Dict[str, InputDefinition]
    outputs: Optional[Dict[str, OutputDefinition]] = None
    description: Optional[str] = None
    module: Optional[str] = None
    class_name: Optional[str] = None
    source: Optional[str] = None
    code: Optional[str] = None
    function: Optional[str] = None
    connection_type: Optional[List[str]] = None
    is_builtin: Optional[bool] = None
    stage: Optional[str] = None
    enable_kwargs: Optional[bool] = False
    deprecated_tools: Optional[List[str]] = None

    def serialize(self) -> dict:
        """Serialize tool to dict and skip None fields.

        :return: The serialized tool
        :rtype: dict
        """

        data = asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None and k != "outputs"})
        if not self.type == ToolType._ACTION:
            return data
        # Pop unused field for action
        skipped_fields = ["type", "inputs", "outputs"]
        return {k: v for k, v in data.items() if k not in skipped_fields}

    @staticmethod
    def deserialize(data: dict) -> "Tool":
        """Deserialize dict to tool.

        :param data: The dict needs to be deserialized
        :type data: dict
        :return: The deserialized tool
        :rtype: ~promptflow.contracts.tool.Tool
        """

        return Tool(
            name=data["name"],
            description=data.get("description", ""),
            type=_deserialize_enum(ToolType, data["type"]),
            inputs={k: InputDefinition.deserialize(i) for k, i in data.get("inputs", {}).items()},
            outputs={k: OutputDefinition.deserialize(o) for k, o in data.get("outputs", {}).items()},
            module=data.get("module"),
            class_name=data.get("class_name"),
            source=data.get("source"),
            code=data.get("code"),
            function=data.get("function"),
            connection_type=data.get("connection_type"),
            is_builtin=data.get("is_builtin"),
            stage=data.get("stage"),
            enable_kwargs=data.get("enable_kwargs", False),
            deprecated_tools=data.get("deprecated_tools"),
        )

    def _require_connection(self) -> bool:
        return self.type is ToolType.LLM or isinstance(self.connection_type, list) and len(self.connection_type) > 0


class ToolFuncCallScenario(str, Enum):
    GENERATED_BY = "generated_by"
    REVERSE_GENERATED_BY = "reverse_generated_by"
    DYNAMIC_LIST = "dynamic_list"
