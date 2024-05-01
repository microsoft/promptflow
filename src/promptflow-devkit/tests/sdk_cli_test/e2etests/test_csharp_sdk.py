from typing import TypedDict

import pytest

from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._pf_client import PFClient

_client = PFClient()


class CSharpProject(TypedDict):
    flow_dir: str
    data: str
    init: str


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.sdk_test
@pytest.mark.e2etest
@pytest.mark.csharp
class TestCSharpSdk:
    @pytest.mark.parametrize(
        "expected_signature",
        [
            pytest.param(
                {
                    "init": {},
                    "inputs": {
                        "language": {"default": "chinese", "type": "string"},
                        "topic": {"default": "ocean", "type": "string"},
                    },
                    "outputs": {
                        "Answer": {"type": "string"},
                        "AnswerLength": {"type": "int"},
                        "PoemLanguage": {"type": "string"},
                    },
                },
                id="function_mode_basic",
            ),
            pytest.param(
                {
                    "init": {"connection": {"type": "AzureOpenAIConnection"}, "name": {"type": "string"}},
                    "inputs": {"question": {"default": "What is Promptflow?", "type": "string"}},
                    "outputs": {"output": {"type": "string"}},
                },
                id="class_init_flex_flow",
            ),
        ],
    )
    def test_pf_run_create(self, request, expected_signature: dict):
        test_case: CSharpProject = request.getfixturevalue(f"csharp_test_project_{request.node.callspec.id}")
        flow = load_flow(test_case["flow_dir"])
        signature = _client.flows._infer_signature(
            flow,
            include_primitive_output=True,
        )
        assert signature == expected_signature
