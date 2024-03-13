from unittest.mock import patch

import pytest
from promptflow.tools.common import ChatAPIInvalidFunctions, validate_functions, process_function_call, \
    parse_chat, find_referenced_image_set, preprocess_template_string, convert_to_chat_list, ChatInputList, \
    ParseConnectionError, _parse_resource_id, list_deployment_connections, \
    normalize_connection_config, in_local_env
from promptflow.tools.exception import ListDeploymentsError

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.contracts.multimedia import Image
from tests.utils import CustomException, Deployment
import os

DEFAULT_SUBSCRIPTION_ID = "sub"
DEFAULT_RESOURCE_GROUP_NAME = "rg"
DEFAULT_WORKSPACE_NAME = "ws"
DEFAULT_ACCOUNT = "account"
DEFAULT_CONNECTION = "conn"


# set environment variable to mock the runtime environment
@pytest.fixture(autouse=True)
def mock_settings_env_vars():
    with patch.dict(
        os.environ,
        {
            "AZUREML_ARM_SUBSCRIPTION": "fake_sub_id",
            "AZUREML_ARM_RESOURCEGROUP": "fake_rg",
            "AZUREML_ARM_WORKSPACE_NAME": "fake_ws",
        },
    ):
        yield


def mock_build_connection_dict_func1(**kwargs):
    from promptflow.azure.operations._arm_connection_operations import OpenURLFailedUserError
    raise OpenURLFailedUserError


def mock_build_connection_dict_func2(**kwargs):
    return {"value": {"resource_id": "abc"}}


def mock_build_connection_dict_func3(**kwargs):
    resource_id = (
        f"/subscriptions/{DEFAULT_SUBSCRIPTION_ID}/resourceGroups/{DEFAULT_RESOURCE_GROUP_NAME}"
        f"/providers/Microsoft.CognitiveServices/accounts/{DEFAULT_ACCOUNT}"
    )
    return {"value": {"resource_id": resource_id}}


class TestCommon:
    @pytest.mark.parametrize(
        "functions, error_message",
        [
            ([], "functions cannot be an empty list"),
            (["str"],
             "is not a dict. Here is a valid function example"),
            ([{"name": "func1"}], "does not have 'parameters' property"),
            ([{"name": "func1", "parameters": "param1"}],
             "should be described as a JSON Schema object"),
            ([{"name": "func1", "parameters": {"type": "int", "properties": {}}}],
             "parameters 'type' should be 'object'"),
            ([{"name": "func1", "parameters": {"type": "object", "properties": []}}],
             "should be described as a JSON Schema object"),
        ],
    )
    def test_chat_api_invalid_functions(self, functions, error_message):
        error_codes = "UserError/ToolValidationError/ChatAPIInvalidFunctions"
        with pytest.raises(ChatAPIInvalidFunctions) as exc_info:
            validate_functions(functions)
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.parametrize(
        "function_call, error_message",
        [
            ("123", "function_call parameter '123' must be a dict"),
            ({"name1": "get_current_weather"},
             'function_call parameter {"name1": "get_current_weather"} must '
             'contain "name" field'),
        ],
    )
    def test_chat_api_invalid_function_call(self, function_call, error_message):
        error_codes = "UserError/ToolValidationError/ChatAPIInvalidFunctions"
        with pytest.raises(ChatAPIInvalidFunctions) as exc_info:
            process_function_call(function_call)
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.parametrize(
        "chat_str, images, expected_result",
        [
            ("system:\nthis is my function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            ("#system:\nthis is my ##function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my ##function:\ndef hello'}]),
            (" \n system:\nthis is my function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            (" \n # system:\nthis is my function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            ("user:\nhi\nassistant:\nanswer\nfunction:\nname:\nn\ncontent:\nc", None, [
                {'role': 'user', 'content': 'hi'},
                {'role': 'assistant', 'content': 'answer'},
                {'role': 'function', 'name': 'n', 'content': 'c'}]),
            ("#user :\nhi\n #assistant:\nanswer\n# function:\n##name:\nn\n##content:\nc", None, [
                {'role': 'user', 'content': 'hi'},
                {'role': 'assistant', 'content': 'answer'},
                {'role': 'function', 'name': 'n', 'content': 'c'}]),
            ("\nsystem:\nfirst\n\nsystem:\nsecond", None, [
                {'role': 'system', 'content': 'first'}, {'role': 'system', 'content': 'second'}]),
            ("\n#system:\nfirst\n\n#system:\nsecond", None, [
                {'role': 'system', 'content': 'first'}, {'role': 'system', 'content': 'second'}]),
            ("\n#system:\nfirst\n#assistant:\n#user:\nsecond", None, [
                {'role': 'system', 'content': 'first'},
                {'role': 'assistant', 'content': ''},
                {'role': 'user', 'content': 'second'}
            ]),
            # todo: enable this test case after we support image_url officially
            # ("#user:\ntell me about the images\nImage(1edf82c2)\nImage(9b65b0f4)", [
            #     Image("image1".encode()), Image("image2".encode(), "image/png", "https://image_url")], [
            #     {'role': 'user', 'content': [
            #         {'type': 'text', 'text': 'tell me about the images'},
            #         {'type': 'image_url', 'image_url': {'url': 'data:image/*;base64,aW1hZ2Ux'}},
            #         {'type': 'image_url', 'image_url': 'https://image_url'}]},
            # ])
        ]
    )
    def test_success_parse_role_prompt(self, chat_str, images, expected_result):
        actual_result = parse_chat(chat_str, images)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        "chat_str, expected_result",
        [
            ("\n#system:\n##name:\nAI \n content:\nfirst\n\n#user:\nsecond", [
                {'role': 'system', 'name': 'AI', 'content': 'first'}, {'role': 'user', 'content': 'second'}]),
            ("\nuser:\nname:\n\nperson\n content:\n", [
                {'role': 'user', 'name': 'person', 'content': ''}]),
            ("\nsystem:\nname:\n\n content:\nfirst", [
                {'role': 'system', 'content': 'name:\n\n content:\nfirst'}]),
            ("\nsystem:\nname:\n\n", [
                {'role': 'system', 'content': 'name:'}])
        ]
    )
    def test_parse_chat_with_name_in_role_prompt(self, chat_str, expected_result):
        actual_result = parse_chat(chat_str)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        "kwargs, expected_result",
        [
            ({}, set()),
            ({"image_1": Image("image1".encode()), "image_2": Image("image2".encode()), "t1": "text"}, {
                Image("image1".encode()), Image("image2".encode())
            }),
            ({"images": [Image("image1".encode()), Image("image2".encode())]}, {
                Image("image1".encode()), Image("image2".encode())
            }),
            ({"image_1": Image("image1".encode()), "image_2": Image("image1".encode())}, {
                Image("image1".encode())
            }),
            ({"images": {"image_1": Image("image1".encode()), "image_2": Image("image2".encode())}}, {
                Image("image1".encode()), Image("image2".encode())
            })
        ]
    )
    def test_find_referenced_image_set(self, kwargs, expected_result):
        actual_result = find_referenced_image_set(kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        "input_string, expected_output",
        [
            ("![image]({{img1}})", "\n{{img1}}\n"),
            ("![image]({{img1}})![image]({{img2}})", "\n{{img1}}\n\n{{img2}}\n"),
            ("No image here", "No image here"),
            ("![image]({{img1}}) Some text ![image]({{img2}})", "\n{{img1}}\n Some text \n{{img2}}\n"),
        ],
    )
    def test_preprocess_template_string(self, input_string, expected_output):
        actual_result = preprocess_template_string(input_string)
        assert actual_result == expected_output

    @pytest.mark.parametrize(
        "input_data, expected_output",
        [
            ({}, {}),
            ({"key": "value"}, {"key": "value"}),
            (["item1", "item2"], ChatInputList(["item1", "item2"])),
            ({"key": ["item1", "item2"]}, {"key": ChatInputList(["item1", "item2"])}),
            (["item1", ["nested_item1", "nested_item2"]],
             ChatInputList(["item1", ChatInputList(["nested_item1", "nested_item2"])])),
        ],
    )
    def test_convert_to_chat_list(self, input_data, expected_output):
        actual_result = convert_to_chat_list(input_data)
        assert actual_result == expected_output

    def test_parse_resource_id(self):
        sub = "dummy_sub"
        rg = "dummy_rg"
        account = "dummy_account"
        resource_id = (
            f"/subscriptions/{sub}/resourceGroups/{rg}/providers/"
            f"Microsoft.CognitiveServices/accounts/{account}"
        )
        parsed_sub, parsed_rg, parsed_account = _parse_resource_id(resource_id)
        assert sub == parsed_sub and rg == parsed_rg and account == parsed_account

    @pytest.mark.parametrize(
        "resource_id, error_message",
        [
            ("", "Connection resourceId format invalid, cur resourceId is "),
            ("a/b/c/d", "Connection resourceId format invalid, cur resourceId is a/b/c/d"),
        ],
    )
    def test_parse_resource_id_with_error(self, resource_id, error_message):
        with pytest.raises(ParseConnectionError, match=error_message):
            _parse_resource_id(resource_id)

    def test_list_deployment_connections_with_conn_error(self, monkeypatch):
        from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations

        monkeypatch.setattr(
            ArmConnectionOperations,
            "_build_connection_dict",
            mock_build_connection_dict_func1
        )
        res = list_deployment_connections(
            DEFAULT_SUBSCRIPTION_ID,
            DEFAULT_RESOURCE_GROUP_NAME,
            DEFAULT_WORKSPACE_NAME,
            DEFAULT_CONNECTION
        )
        assert res is None

    def test_list_deployment_connections_with_wrong_connection_id(self, monkeypatch):
        from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations

        monkeypatch.setattr(
            ArmConnectionOperations,
            "_build_connection_dict",
            mock_build_connection_dict_func2
        )
        with pytest.raises(ListDeploymentsError):
            list_deployment_connections(
                DEFAULT_SUBSCRIPTION_ID,
                DEFAULT_RESOURCE_GROUP_NAME,
                DEFAULT_WORKSPACE_NAME,
                DEFAULT_CONNECTION,
            )

    def test_list_deployment_connections_with_permission_issue(self, monkeypatch):
        from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations

        monkeypatch.setattr(
            ArmConnectionOperations,
            "_build_connection_dict",
            mock_build_connection_dict_func3
        )
        with patch('azure.mgmt.cognitiveservices.CognitiveServicesManagementClient') as mock:
            mock.side_effect = CustomException("", 403)
            with pytest.raises(ListDeploymentsError) as excinfo:
                list_deployment_connections(
                    DEFAULT_SUBSCRIPTION_ID,
                    DEFAULT_RESOURCE_GROUP_NAME,
                    DEFAULT_WORKSPACE_NAME,
                    DEFAULT_CONNECTION,
                )
            assert "Failed to list deployments due to permission issue" in str(excinfo.value)

    def test_list_deployment_connections(self, monkeypatch):
        from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations
        from azure.ai.ml._azure_environments import AzureEnvironments

        monkeypatch.setattr(
            ArmConnectionOperations,
            "_build_connection_dict",
            mock_build_connection_dict_func3
        )
        with (
            patch('azure.ai.ml._azure_environments._get_default_cloud_name') as mock_cloud_name,
            patch('azure.mgmt.cognitiveservices.CognitiveServicesManagementClient') as mock
        ):
            mock_cloud_name.return_value = AzureEnvironments.ENV_DEFAULT
            instance = mock.return_value
            instance.deployments.list.return_value = {
                Deployment("deployment1", "model1", "vision-preview"),
                Deployment("deployment2", "model2", "version2")
            }
            res = list_deployment_connections(
                DEFAULT_SUBSCRIPTION_ID,
                DEFAULT_RESOURCE_GROUP_NAME,
                DEFAULT_WORKSPACE_NAME,
                DEFAULT_CONNECTION
            )
            assert len(res) == 2

    def test_list_deployment_connections_sovereign_credential(self, monkeypatch):
        from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations
        from azure.ai.ml._azure_environments import AzureEnvironments

        monkeypatch.setattr(
            ArmConnectionOperations,
            "_build_connection_dict",
            mock_build_connection_dict_func3
        )
        with (
            patch('azure.ai.ml._azure_environments._get_default_cloud_name') as mock_cloud_name,
            patch('azure.ai.ml._azure_environments._get_cloud') as mock_cloud,
            patch('azure.identity.DefaultAzureCredential') as mock_cre,
            patch('azure.mgmt.cognitiveservices.CognitiveServicesManagementClient') as mock
        ):
            mock_cloud_name.return_value = AzureEnvironments.ENV_CHINA
            cloud = mock_cloud.return_value
            cloud.get.return_value = "authority"
            mock_cre.return_value = "credential"
            instance = mock.return_value
            instance.deployments.list.return_value = {
                Deployment("deployment1", "model1", "vision-preview"),
                Deployment("deployment2", "model2", "version2")
            }
            res = list_deployment_connections(
                DEFAULT_SUBSCRIPTION_ID,
                DEFAULT_RESOURCE_GROUP_NAME,
                DEFAULT_WORKSPACE_NAME,
                DEFAULT_CONNECTION
            )
            assert len(res) == 2

    @pytest.mark.parametrize(
        "input_data, expected_output",
        [
            (OpenAIConnection(api_key="fake_key", organization="fake_org", base_url="https://openai"),
             {"max_retries": 0, "api_key": "fake_key", "organization": "fake_org", "base_url": "https://openai"}),
            (AzureOpenAIConnection(api_key="fake_key", api_base="https://aoai", api_version="v1"),
             {"max_retries": 0, "api_key": "fake_key", "api_version": "v1", "azure_endpoint": "https://aoai"}),
        ]
    )
    def test_normalize_connection_config(self, input_data, expected_output):
        actual_result = normalize_connection_config(input_data)
        assert actual_result == expected_output

    def test_normalize_connection_config_for_aoai_meid(self):
        aoai_meid_connection = AzureOpenAIConnection(
            api_base="https://aoai",
            api_version="v1",
            auth_mode="meid_token")
        normalized_config = normalize_connection_config(aoai_meid_connection)
        expected_output = {
            "max_retries": 0,
            "api_version": "v1",
            "azure_endpoint": "https://aoai",
            "azure_ad_token_provider": aoai_meid_connection.get_token
        }
        assert normalized_config == expected_output

    def test_is_in_local_env(self):
        assert not in_local_env()

        with patch.dict('os.environ', values={}, clear=True):
            assert in_local_env()
