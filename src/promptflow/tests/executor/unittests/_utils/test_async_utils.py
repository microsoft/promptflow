from unittest.mock import patch

import pytest

from promptflow._utils.async_utils import async_run_allowing_running_loop


@pytest.mark.unittest
class TestAsyncUtils:
    @pytest.mark.parametrize("has_running_loop,num1,num2,expected_result", [(False, 1, 2, 3), (True, 3, 4, 7)])
    def test_async_run_allowing_running_loop(self, has_running_loop, num1, num2, expected_result):
        async def async_func_to_test(a, b):
            return a + b

        with patch("promptflow._utils.async_utils._has_running_loop", return_value=has_running_loop):
            result = async_run_allowing_running_loop(async_func_to_test, num1, num2)
            assert result == expected_result
