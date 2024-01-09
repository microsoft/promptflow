import pytest
import os
from unittest.mock import patch

from promptflow._utils.utils import is_json_serializable, get_int_env_var


class MyObj:
    pass


@pytest.mark.unittest
class TestUtils:
    @pytest.mark.parametrize("value, expected_res", [(None, True), (1, True), ("", True), (MyObj(), False)])
    def test_is_json_serializable(self, value, expected_res):
        assert is_json_serializable(value) == expected_res

    @pytest.mark.parametrize(
        "env_var, env_value, default_value, expected_result",
        [
            ("TEST_VAR", "10", None, 10),          # Valid integer string
            ("TEST_VAR", "invalid", None, None),   # Invalid integer strings
            ("TEST_VAR", None, 5, 5),              # Environment variable does not exist
            ("TEST_VAR", "10", 5, 10),             # Valid integer string with a default value
            ("TEST_VAR", "invalid", 5, 5),         # Invalid integer string with a default value
        ])
    def test_get_int_env_var(self, env_var, env_value, default_value, expected_result):
        with patch.dict(os.environ, {env_var: env_value} if env_value is not None else {}):
            assert get_int_env_var(env_var, default_value) == expected_result

    @pytest.mark.parametrize(
        "env_var, env_value, expected_result",
        [
            ("TEST_VAR", "10", 10),             # Valid integer string
            ("TEST_VAR", "invalid", None),      # Invalid integer strings
            ("TEST_VAR", None, None),           # Environment variable does not exist
        ])
    def test_get_int_env_var_without_default_vaue(self, env_var, env_value, expected_result):
        with patch.dict(os.environ, {env_var: env_value} if env_value is not None else {}):
            assert get_int_env_var(env_var) == expected_result
