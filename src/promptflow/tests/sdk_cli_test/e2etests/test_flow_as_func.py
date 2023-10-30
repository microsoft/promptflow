# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from types import GeneratorType

import pytest

from promptflow import load_flow
from promptflow._sdk.entities import CustomConnection
from promptflow.entities import FlowContext
from promptflow.exceptions import UserErrorException

FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
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

    def test_stream_output(self):
        f = load_flow(f"{FLOWS_DIR}/chat_flow_with_stream_output")
        f.context.streaming = True
        result = f(
            chat_history=[
                {"inputs": {"chat_input": "Hi"}, "outputs": {"chat_output": "Hello! How can I assist you today?"}}
            ]
        )
        assert isinstance(result["answer"], GeneratorType)

    def test_environment_variables(self):
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        f.context.environment_variables = {"key": "value"}
        result = f(key="key")
        assert result["output"] == "value"

    def test_flow_as_a_func_with_variant(self):
        flow_path = Path(f"{FLOWS_DIR}/web_classification").absolute()
        f = load_flow(
            flow_path,
        )
        f.context.variant = "${summarize_text_content.variant_0}"

        f(url="https://www.youtube.com/watch?v=o5ZQyXaAv1g")
