# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from promptflow.sdk._utils import decrypt_secret_value, encrypt_secret_value, snake_to_camel

TEST_ROOT = Path(__file__).parent.parent.parent
CONNECTION_ROOT = TEST_ROOT / "test_configs/flows/connections"


@pytest.mark.unittest
class TestUtils:
    def test_encrypt_decrypt_value(self):
        test_value = "test"
        encrypted = encrypt_secret_value(test_value)
        assert decrypt_secret_value("mock", encrypted) == test_value

    def test_snake_to_camel(self):
        assert snake_to_camel("test_snake_case") == "TestSnakeCase"
        assert snake_to_camel("TestSnakeCase") == "TestSnakeCase"
