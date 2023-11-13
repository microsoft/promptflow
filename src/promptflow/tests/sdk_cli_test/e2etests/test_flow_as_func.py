# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from types import GeneratorType

import pytest

from promptflow import load_flow
from promptflow._sdk._errors import ConnectionNotFoundError, InvalidFlowError
from promptflow._sdk.entities import CustomConnection
from promptflow.entities import FlowContext
from promptflow.exceptions import UserErrorException

from ..recording_utilities import RecordStorage

FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures(
    "use_secrets_config_file", "setup_local_connection", "install_custom_tool_pkg", "recording_injection"
)
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowAsFunc:
    def test_flow_as_a_func(self):
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        result = f(key="unknown")
        assert result["output"] is None

    def test_flow_as_a_func_with_connection_overwrite(self):
        from promptflow._sdk._errors import ConnectionNotFoundError

        f = load_flow(f"{FLOWS_DIR}/web_classification")
        f.context.connections = {"classify_with_llm": {"connection": "not_exist"}}

        with pytest.raises(ConnectionNotFoundError) as e:
            f(url="https://www.youtube.com/watch?v=o5ZQyXaAv1g")
        assert "Connection 'not_exist' is not found" in str(e.value)

    @pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="TODO: support customized python tool in future")
    def test_flow_as_a_func_with_connection_obj(self):
        f = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        f.context.connections = {"hello_node": {"connection": CustomConnection(secrets={"k": "v"})}}

        result = f(text="hello")
        assert result["output"]["secrets"] == {"k": "v"}

    def test_overrides(self):
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        f.context = FlowContext(
            environment_variables={"provided_key": "provided_value"},
            # node print_env will take "provided_key" instead of flow input
            overrides={"nodes.print_env.inputs.key": "provided_key"},
        )
        # the key="unknown" will not take effect
        result = f(key="unknown")
        assert result["output"] == "provided_value"

    @pytest.mark.skip(reason="This experience has not finalized yet.")
    def test_flow_as_a_func_with_token_based_connection(self):
        class MyCustomConnection(CustomConnection):
            def get_token(self):
                return "fake_token"

        f = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        f.context.connections = {"hello_node": {"connection": MyCustomConnection(secrets={"k": "v"})}}

        result = f(text="hello")
        assert result == {}

    def test_exception_handle(self):
        f = load_flow(f"{FLOWS_DIR}/flow_with_invalid_import")
        with pytest.raises(UserErrorException) as e:
            f(text="hello")
        assert "Failed to load python module " in str(e.value)

        f = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        with pytest.raises(UserErrorException) as e:
            f()
        assert "Required input(s) ['text'] are missing" in str(e.value)

    @pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Stream not supported in replaying mode.")
    def test_stream_output(self):
        f = load_flow(f"{FLOWS_DIR}/chat_flow_with_python_node_streaming_output")
        f.context.streaming = True
        result = f(
            chat_history=[
                {"inputs": {"chat_input": "Hi"}, "outputs": {"chat_output": "Hello! How can I assist you today?"}}
            ],
            question="How are you?",
        )
        assert isinstance(result["answer"], GeneratorType)

    def test_environment_variables(self):
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        f.context.environment_variables = {"key": "value"}
        result = f(key="key")
        assert result["output"] == "value"

    def test_flow_as_a_func_with_variant(self):
        flow_path = Path(f"{FLOWS_DIR}/flow_with_dict_input_with_variant").absolute()
        f = load_flow(
            flow_path,
        )
        f.context.variant = "${print_val.variant1}"
        # variant1 will use a mock_custom_connection
        with pytest.raises(ConnectionNotFoundError) as e:
            f(key="a")
        assert "Connection 'mock_custom_connection' is not found." in str(e.value)

        # non-exist variant
        f.context.variant = "${print_val.variant_2}"
        with pytest.raises(InvalidFlowError) as e:
            f(key="a")
        assert "Variant variant_2 not found for node print_val" in str(e.value)

    def test_non_scrubbed_connection(self):
        f = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        f.context.connections = {"hello_node": {"connection": CustomConnection(secrets={"k": "*****"})}}

        with pytest.raises(UserErrorException) as e:
            f(text="hello")
        assert "please make sure connection has decrypted secrets to use in flow execution." in str(e)

    def test_local_connection_object(self, pf, azure_open_ai_connection):
        f = load_flow(f"{FLOWS_DIR}/web_classification")
        f.context.connections = {"classify_with_llm": {"connection": azure_open_ai_connection}}
        f()

        # local connection without secret will lead to error
        connection = pf.connections.get("azure_open_ai_connection", with_secrets=False)
        f.context.connections = {"classify_with_llm": {"connection": connection}}
        with pytest.raises(UserErrorException) as e:
            f()
        assert "please make sure connection has decrypted secrets to use in flow execution." in str(e)

    def test_non_secret_connection(self):
        f = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        # execute connection without secrets won't get error since the connection doesn't have scrubbed secrets
        # we only raise error when there are scrubbed secrets in connection
        f.context.connections = {"hello_node": {"connection": CustomConnection(secrets={})}}
        f(text="hello")
