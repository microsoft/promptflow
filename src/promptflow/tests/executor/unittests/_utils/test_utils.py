import pytest

from promptflow._utils.utils import is_json_serializable


class MyObj:
    pass


@pytest.mark.unittest
class TestUtils:
    @pytest.mark.parametrize("value, expected_res", [(None, True), (1, True), ("", True), (MyObj(), False)])
    def test_is_json_serializable(self, value, expected_res):
        assert is_json_serializable(value) == expected_res
