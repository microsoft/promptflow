# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from types import GeneratorType

import pytest

from promptflow import load_flow
from promptflow._sdk._errors import ConnectionNotFoundError, InvalidFlowError
from promptflow._sdk.entities import CustomConnection
from promptflow._sdk.operations._flow_conext_resolver import FlowContextResolver
from promptflow.entities import FlowContext
from promptflow.exceptions import UserErrorException

FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowAsFunc:
    def test_flow_as_a_func(self):
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        result = f(key="unknown")
        assert result["output"] is None
        assert "line_number" not in result

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

        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        with pytest.raises(UserErrorException) as e:
            f()
        assert "Required input(s) ['key'] are missing" in str(e.value)

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
        f = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        # local connection without secret will lead to error
        connection = pf.connections.get("azure_open_ai_connection", with_secrets=False)
        f.context.connections = {"hello_node": {"connection": connection}}
        with pytest.raises(UserErrorException) as e:
            f(text="hello")
        assert "please make sure connection has decrypted secrets to use in flow execution." in str(e)

    def test_non_secret_connection(self):
        f = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        # execute connection without secrets won't get error since the connection doesn't have scrubbed secrets
        # we only raise error when there are scrubbed secrets in connection
        f.context.connections = {"hello_node": {"connection": CustomConnection(secrets={})}}
        f(text="hello")

    def test_flow_context_cache(self):
        # same flow context has same hash
        assert hash(FlowContext()) == hash(FlowContext())
        # getting executor for same flow will hit cache
        flow_path = Path(f"{FLOWS_DIR}/print_env_var")
        flow_executor1 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(),
        )
        flow_executor2 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(),
        )
        assert flow_executor1 is flow_executor2

        # getting executor for same flow + context will hit cache
        flow_path = Path(f"{FLOWS_DIR}/flow_with_custom_connection")
        flow_executor1 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k": "v"})}}),
        )
        flow_executor2 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k": "v"})}}),
        )
        assert flow_executor1 is flow_executor2

        flow_path = Path(f"{FLOWS_DIR}/flow_with_dict_input_with_variant")
        flow_executor1 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(
                variant="${print_val.variant1}",
                connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
                overrides={"nodes.print_val.inputs.key": "a"},
            ),
        )
        flow_executor2 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(
                variant="${print_val.variant1}",
                connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
                overrides={"nodes.print_val.inputs.key": "a"},
            ),
        )
        assert flow_executor1 is flow_executor2

    def test_flow_context_cache_not_hit(self):
        flow_path = Path(f"{FLOWS_DIR}/flow_with_custom_connection")
        flow_executor1 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k": "v"})}}),
        )
        flow_executor2 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k2": "v"})}}),
        )
        assert flow_executor1 is not flow_executor2

        flow_path = Path(f"{FLOWS_DIR}/flow_with_dict_input_with_variant")
        flow_executor1 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(
                variant="${print_val.variant1}",
                connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
                overrides={"nodes.print_val.inputs.key": "a"},
            ),
        )
        flow_executor2 = FlowContextResolver.create(
            flow_path=flow_path,
            flow_context=FlowContext(
                variant="${print_val.variant1}",
                connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
                overrides={"nodes.print_val.inputs.key": "b"},
            ),
        )
        assert flow_executor1 is not flow_executor2

    @pytest.mark.timeout(10)
    def test_flow_as_func_perf_test(self):
        # this test should not take long due to caching logic
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        for i in range(100):
            f(key="key")
