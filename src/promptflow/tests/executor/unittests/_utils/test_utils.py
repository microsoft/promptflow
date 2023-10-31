import pytest

from promptflow._utils.utils import calculate_execution_time, is_json_serializable


class MyObj:
    pass


# mock functions for calculate_execution_time testing
def mock_dynamic_list_func1():
    pass


def mock_dynamic_list_func2(input1):
    pass


def mock_dynamic_list_func3(input1, input2):
    pass


def mock_dynamic_list_func4(input1, input2, **kwargs):
    pass


def mock_dynamic_list_func5(input1, input2, subscription_id):
    pass


def mock_dynamic_list_func6(input1, input2, subscription_id, resource_group_name, workspace_name):
    pass


@pytest.mark.unittest
class TestUtils:
    @pytest.mark.parametrize("value, expected_res", [(None, True), (1, True), ("", True), (MyObj(), False)])
    def test_is_json_serializable(self, value, expected_res):
        assert is_json_serializable(value) == expected_res

    @pytest.mark.parametrize(
        "func, combined_func_input_params",
        [
            (mock_dynamic_list_func1, {}),
            (mock_dynamic_list_func2, {"input1": 1}),
            (mock_dynamic_list_func3, {"input1": 1, "input2": 2}),
            (
                mock_dynamic_list_func4,
                {
                    "input1": 1,
                    "input2": 2,
                    "subscription_id": "123",
                    "resource_group_name": "rg",
                    "workspace_name": "ws",
                },
            ),
            (mock_dynamic_list_func5, {"input1": 1, "input2": 2, "subscription_id": "123"}),
            (
                mock_dynamic_list_func6,
                {
                    "input1": 1,
                    "input2": 2,
                    "subscription_id": "123",
                    "resource_group_name": "rg",
                    "workspace_name": "ws",
                },
            ),
        ],
    )
    def test_calculate_execution_time(self, func, combined_func_input_params):
        calculate_execution_time(func, **combined_func_input_params)
