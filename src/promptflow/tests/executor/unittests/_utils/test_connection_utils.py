import pytest

from promptflow._sdk.entities import CustomStrongTypeConnection
from promptflow._utils.connection_utils import (
    generate_custom_strong_type_connection_spec,
    generate_custom_strong_type_connection_template,
)
from promptflow.contracts.types import Secret


class MyCustomConnectionWithNoComments(CustomStrongTypeConnection):
    api_key: Secret
    api_base: str


class MyCustomConnectionWithDefaultValue(CustomStrongTypeConnection):
    api_key: Secret
    api_base: str = "default value of api-base"


class MyCustomConnectionWithInvalidComments(CustomStrongTypeConnection):
    """My custom connection with invalid comments.
    :param api_key: The api key.
    :type api_key: String
    :param api_base: The api base.
    :type api_base: String
    :param api_key_2: The api key 2.
    :type api_key_2: String
    """

    api_key: Secret
    api_base: str


class MyCustomConnectionMissingTypeComments(CustomStrongTypeConnection):
    """My custom connection with missing type comments.
    :param api_key: The api key.
    """

    api_key: Secret
    api_base: str


class MyCustomConnectionMissingParamComments(CustomStrongTypeConnection):
    """My custom connection with missing param comments.
    :type api_key: String
    """

    api_key: Secret
    api_base: str


@pytest.mark.unittest
class TestConnectionUtils:
    @pytest.mark.parametrize(
        "cls, expected_str_in_template",
        [
            (
                MyCustomConnectionWithNoComments,
                ['api_base: "to_replace_with_api_base"\n', 'api_key: "to_replace_with_api_key"\n'],
            ),
            (
                MyCustomConnectionWithInvalidComments,
                [
                    'api_base: "to_replace_with_api_base"  # String type. The api base.\n',
                    'api_key: "to_replace_with_api_key"  # String type. The api key.\n',
                ],
            ),
            (MyCustomConnectionMissingTypeComments, ['api_key: "to_replace_with_api_key"  # The api key.']),
            (MyCustomConnectionMissingParamComments, ['api_key: "to_replace_with_api_key"  # String type.']),
        ],
    )
    def test_generate_custom_strong_type_connection_template_with_comments(self, cls, expected_str_in_template):
        package = "test-package"
        package_version = "0.0.1"
        spec = generate_custom_strong_type_connection_spec(cls, package, package_version)
        template = generate_custom_strong_type_connection_template(cls, spec, package, package_version)
        for comment in expected_str_in_template:
            assert comment in template

    def test_generate_custom_strong_type_connection_template_with_default_value(self):
        package = "test-package"
        package_version = "0.0.1"
        spec = generate_custom_strong_type_connection_spec(MyCustomConnectionWithDefaultValue, package, package_version)
        template = generate_custom_strong_type_connection_template(
            MyCustomConnectionWithDefaultValue, spec, package, package_version
        )
        assert 'api_base: "default value of api-base"' in template

    @pytest.mark.parametrize(
        "input_value, expected_connection_names",
        [
            pytest.param(
                "new_ai_connection",
                ["new_ai_connection"],
                id="standard",
            ),
            pytest.param(
                "${node.output}",
                [],
                id="output_reference",
            ),
            pytest.param(
                "${inputs.question}",
                [],
                id="input_reference",
            ),
        ],
    )
    def test_get_used_connection_names_from_flow_meta(self, input_value: str, expected_connection_names: list):
        from promptflow._sdk._orchestrator.utils import SubmitterHelper

        connection_names = SubmitterHelper.get_used_connection_names(
            {
                "package": {
                    "(Promptflow.Tools)Promptflow.Tools.BuiltInTools.AOAI.Chat": {
                        "name": "Promptflow.Tools.BuiltInTools.AOAI.Chat",
                        "type": "csharp",
                        "inputs": {
                            "connection": {"type": ["AzureOpenAIConnection"]},
                            "prompt": {"type": ["string"]},
                            "deployment_name": {"type": ["string"]},
                            "objects": {"type": ["object"]},
                        },
                        "description": "",
                        "class_name": "AOAI",
                        "module": "Promptflow.Tools.BuiltInTools.AOAI",
                        "function": "Chat",
                        "is_builtin": True,
                        "package": "Promptflow.Tools",
                        "package_version": "0.0.14.0",
                        "toolId": "(Promptflow.Tools)Promptflow.Tools.BuiltInTools.AOAI.Chat",
                    },
                },
                "code": {},
            },
            {
                "nodes": [
                    {
                        "name": "get_summarized_text_content",
                        "type": "csharp",
                        "source": {
                            "type": "package",
                            "tool": "(Promptflow.Tools)Promptflow.Tools.BuiltInTools.AOAI.Chat",
                        },
                        "inputs": {
                            "connection": input_value,
                        },
                    },
                ]
            },
        )
        assert connection_names == expected_connection_names
