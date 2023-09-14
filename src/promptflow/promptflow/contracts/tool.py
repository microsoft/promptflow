# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

from promptflow._constants import CONNECTION_NAME_PROPERTY

from .types import PromptTemplate, Secret

T = TypeVar("T", bound="Enum")


def _deserialize_enum(cls: Type[T], val) -> T:
    if not all(isinstance(i, str) for i in cls):
        return val
    typ = next((i for i in cls if val.lower() == i.lower()), None)
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

    @staticmethod
    def from_value(t: Any) -> "ValueType":
        """Get `ValueType` by value.

        :param t: The value needs to get its `ValueType`
        :type t: Any
        :return: The `ValueType` of the given value
        :rtype: ValueType
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
        if isinstance(t, str):
            return ValueType.STRING
        if isinstance(t, list):
            return ValueType.LIST
        return ValueType.OBJECT

    @staticmethod
    def from_type(t: type) -> "ValueType":
        """Get `ValueType` by type.

        :param t: The type needs to get its `ValueType`
        :type t: type
        :return: The `ValueType` of the given type
        :rtype: ValueType
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
        return ValueType.OBJECT

    def parse(self, v: Any) -> Any:  # noqa: C901
        """Parse value to the given `ValueType`.

        :param v: The value needs to be parsed to the given `ValueType`
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
        return val in connections.values()

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

    def serialize(self) -> dict:
        """Serialize `InputDefinition` to dict.

        :return: The serialized `InputDefinition`
        :rtype: dict
        """

        data = {}
        data["type"] = ([t.value for t in self.type],)
        if len(self.type) == 1:
            data["type"] = self.type[0].value
        if self.default:
            data["default"] = str(self.default)
        if self.description:
            data["description"] = self.description
        if self.enum:
            data["enum"] = self.enum
        return data

    @staticmethod
    def deserialize(data: dict) -> "InputDefinition":
        """Deserialize dict to `InputDefinition`.

        :param data: The dict needs to be deserialized
        :type data: dict
        :return: The deserialized `InputDefinition`
        :rtype: InputDefinition
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
        )


@dataclass
class OutputDefinition:
    """Output definition."""

    type: List["ValueType"]
    description: str = ""
    is_property: bool = False

    def serialize(self) -> dict:
        """Serialize `OutputDefinition` to dict.

        :return: The serialized `OutputDefinition`
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
        """Deserialize dict to `OutputDefinition`.

        :param data: The dict needs to be deserialized
        :type data: dict
        :return: The deserialized `OutputDefinition`
        :rtype: OutputDefinition
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
    :type type: `ToolType`
    :param inputs: The inputs of the tool
    :type inputs: Dict[str, `InputDefinition`]
    :param outputs: The outputs of the tool
    :type outputs: Dict[str, `OutputDefinition`], optional
    :param description: The description of the tool
    :type description: str, optional
    :param module: The module of the tool
    :type module: str, optional
    :param class_name: The class name of the tool
    :type class_name: str, optional
    :param source: The source of the tool
    :type source: str, optional
    :param code: The code of the tool
    :type code: str, optional
    :param function: The function of the tool
    :type function: str, optional
    :param connection_type: The connection type of the tool
    :type connection_type: List[str], optional
    :param is_builtin: Whether the tool is a built-in tool
    :type is_builtin: bool, optional
    :param stage: The stage of the tool
    :type stage: str, optional
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

    def serialize(self) -> dict:
        """Serialize `Tool` to dict and skip None fields.

        :return: The serialized `Tool`
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
        """Deserialize dict to `Tool`.

        :param data: The dict needs to be deserialized
        :type data: dict
        :return: The deserialized `Tool`
        :rtype: Tool
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
        )

    def _require_connection(self) -> bool:
        return self.type is ToolType.LLM or isinstance(self.connection_type, list) and len(self.connection_type) > 0
