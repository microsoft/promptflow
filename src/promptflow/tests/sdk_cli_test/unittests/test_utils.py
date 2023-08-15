# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

import pytest

from promptflow._cli._utils import list_of_dict_to_nested_dict
from promptflow._sdk._utils import (
    decrypt_secret_value,
    encrypt_secret_value,
    snake_to_camel,
)

TEST_ROOT = Path(__file__).parent.parent.parent
CONNECTION_ROOT = TEST_ROOT / "test_configs/connections"


@pytest.mark.unittest
class TestUtils:
    def test_encrypt_decrypt_value(self):
        test_value = "test"
        encrypted = encrypt_secret_value(test_value)
        assert decrypt_secret_value("mock", encrypted) == test_value

    def test_snake_to_camel(self):
        assert snake_to_camel("test_snake_case") == "TestSnakeCase"
        assert snake_to_camel("TestSnakeCase") == "TestSnakeCase"

    def test_list_of_dict_to_nested_dict(self):
        test_list = [{"node1.connection": "a"}, {"node2.deploy_name": "b"}]
        result = list_of_dict_to_nested_dict(test_list)
        assert result == {"node1": {"connection": "a"}, "node2": {"deploy_name": "b"}}
        test_list = [{"node1.connection": "a"}, {"node1.deploy_name": "b"}]
        result = list_of_dict_to_nested_dict(test_list)
        assert result == {"node1": {"connection": "a", "deploy_name": "b"}}

    def test_sqlite_retry(self, capfd) -> None:
        from sqlalchemy.exc import OperationalError

        from promptflow._sdk._orm.retry import sqlite_retry

        @sqlite_retry
        def mock_sqlite_op() -> None:
            print("sqlite op...")
            raise OperationalError("statement", "params", "orig")

        # it will finally raise an OperationalError
        with pytest.raises(OperationalError):
            mock_sqlite_op()
        # assert function execution time from stdout
        out, _ = capfd.readouterr()
        assert out.count("sqlite op...") == 3
