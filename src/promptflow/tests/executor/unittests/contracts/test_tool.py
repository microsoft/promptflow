from typing import Any, Callable, NewType, Optional, Tuple, TypeVar, Union

import pytest

from promptflow._sdk.entities import CustomStrongTypeConnection
from promptflow.contracts.tool import ConnectionType


class MyConnection(CustomStrongTypeConnection):
    pass


my_connection = MyConnection(name="my_connection", secrets={"key": "value"})


def some_function():
    pass


@pytest.mark.unittest
class TestToolContract:
    @pytest.mark.parametrize(
        "val, expected_res",
        [
            (my_connection, True),
            (MyConnection, True),
            (list, False),
            (list[str], False),
            (list[int], False),
            ([1, 2, 3], False),
            (float, False),
            (int, False),
            (5, False),
            (str, False),
            (some_function, False),
            (Union[str, int], False),
            # ((int | str), False), # Python 3.10
            (tuple, False),
            (tuple[str, int], False),
            (Tuple[int, ...], False),
            (dict[str, Any], False),
            ({"test1": [1, 2, 3], "test2": [4, 5, 6], "test3": [7, 8, 9]}, False),
            (Any, False),
            (None, False),
            (Optional[str], False),
            (TypeVar("T"), False),
            (TypeVar, False),
            (Callable, False),
            (Callable[..., Any], False),
            (NewType("MyType", int), False),
        ],
    )
    def test_is_custom_strong_type(self, val, expected_res):
        assert ConnectionType.is_custom_strong_type(val) == expected_res
