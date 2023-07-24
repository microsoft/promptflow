from enum import Enum
from typing import Union

from .error_codes import InvalidAzureStorageMode, InvalidValueType


class AzureStorageMode(int, Enum):
    Table = 0
    Blob = 1

    @classmethod
    def parse(cls, value: Union[str, int]):
        """Parse string to RunMode."""
        if isinstance(value, int):
            return AzureStorageMode(value)
        if not isinstance(value, str):
            raise InvalidValueType(
                message_format="Invalid value type to parse, expected: string, but got: {value_type}",
                value_type=type(value),
            )
        if value == "Table":
            return AzureStorageMode.Table
        elif value == "Blob":
            return AzureStorageMode.Blob
        else:
            raise InvalidAzureStorageMode(
                message_format="Invalid value to parse: {value}. Must be 'Table' or 'Blob'.", value=value
            )
