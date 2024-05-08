# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import GeneratorType

import mock
import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._errors import ConnectionNotFoundError, InvalidFlowError
from promptflow._sdk.entities import CustomConnection
from promptflow._sdk.entities._flows._flow_context_resolver import FlowContextResolver
from promptflow._utils.flow_utils import dump_flow_yaml_to_existing_path, load_flow_dag
from promptflow.client import load_flow
from promptflow.entities import FlowContext
from promptflow.exceptions import UserErrorException

FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/flows"
RUNS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/runs"
DATAS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/datas"


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowAsFunc:
    @pytest.mark.parametrize(
        "test_folder",
        [
            f"{FLOWS_DIR}/print_env_var",
            f"{FLOWS_DIR}/print_env_var_async",
        ],
    )
    def test_flow_as_a_func(self, test_folder):
        f = load_flow(test_folder)
        result = f(key="unknown")
        assert result["output"] is None
        assert "line_number" not in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "async_call_folder",
        [
            f"{FLOWS_DIR}/print_env_var",
            f"{FLOWS_DIR}/print_env_var_async",
        ],
    )
    async def test_flow_as_a_func_asynckw(self, async_call_folder):
        from promptflow.core._flow import AsyncFlow

        f = AsyncFlow.load(async_call_folder)
        result = await f(key="PATH")
        assert result["output"] is not None

    @pytest.mark.asyncio
    async def test_flow_as_a_func_real_async(self):
        from promptflow.core._flow import AsyncFlow

        original_async_func = AsyncFlow.invoke

        # Modify the original function and retrieve the time info.
        run_info_group = []
        node_run_infos_group = []

        async def parse_invoke_async(*args, **kwargs):
            nonlocal run_info_group, node_run_infos_group
            obj = await original_async_func(*args, **kwargs)
            run_info_group.append(obj.run_info)
            node_run_infos_group.append(obj.node_run_infos)
            return obj

        with mock.patch("promptflow.core._flow.AsyncFlow.invoke", parse_invoke_async):
            f_async_tools = AsyncFlow.load(f"{FLOWS_DIR}/async_tools")
            f_env_var_async = AsyncFlow.load(f"{FLOWS_DIR}/print_env_var_async")

            time_start = datetime.now()
            results = await asyncio.gather(
                f_async_tools(input_str="Hello"), f_async_tools(input_str="World"), f_env_var_async(key="PATH")
            )
            assert len(results) == 3
            time_spent_flows = datetime.now() - time_start

            # async_tools dag structure:
            # Node1(3 seconds) -> Node2(3 seconds)
            #                  -> Node3(3 seconds)
            # print_env_var_async dag structure:
            # get_env_var(1 second)
            # Time assertion: flow running time should be quite less than sum of all node running time.
            # The time spent of get_env_var is far less than the time spent of async_tools.

            # Here is the time assertion of async_tools:
            # Flow running time should be quite less than sum of all node running time.
            time_spent_run = run_info_group[1].end_time - run_info_group[1].start_time
            time_spent_nodes = []
            for _, node_run_info in node_run_infos_group[1].items():
                time_spent = node_run_info.end_time - node_run_info.start_time
                time_spent_nodes.append(time_spent)
            # All three node running time should be less than the total flow running time
            sum_time_nodes = time_spent_nodes[0] + time_spent_nodes[1] + time_spent_nodes[2]
            assert time_spent_run < sum_time_nodes

            # Here is the time assertion of all flows:
            # Group running time should less than the total flow running time
            sum_running_time = [run_info.end_time - run_info.start_time for run_info in run_info_group]
            assert time_spent_flows < sum_running_time[0] + sum_running_time[1] + sum_running_time[2]

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
        assert result["output"] == {"k": "v"}

    def test_overrides(self):
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        f.context = FlowContext(
            # node print_env will take "provided_key" instead of flow input
            overrides={"nodes.print_env.inputs.key": "provided_key"},
        )
        # the key="unknown" will not take effect
        result = f(key="unknown")
        assert result["output"] is None

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
        assert "Required input fields ['key'] are missing" in str(e.value)

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

    @pytest.mark.skip(reason="This experience has not finalized yet.")
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
        flow1 = load_flow(f"{FLOWS_DIR}/print_env_var")
        flow2 = load_flow(f"{FLOWS_DIR}/print_env_var")
        flow_executor1 = FlowContextResolver.resolve(
            flow=flow1,
        )
        flow_executor2 = FlowContextResolver.resolve(
            flow=flow2,
        )
        assert flow_executor1 is flow_executor2

        # getting executor for same flow + context will hit cache
        flow1 = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        flow1.context = FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k": "v"})}})
        flow2 = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        flow2.context = FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k": "v"})}})
        flow_executor1 = FlowContextResolver.resolve(
            flow=flow1,
        )
        flow_executor2 = FlowContextResolver.resolve(
            flow=flow2,
        )
        assert flow_executor1 is flow_executor2

        flow1 = load_flow(f"{FLOWS_DIR}/flow_with_dict_input_with_variant")
        flow1.context = FlowContext(
            variant="${print_val.variant1}",
            connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
            overrides={"nodes.print_val.inputs.key": "a"},
        )
        flow2 = load_flow(f"{FLOWS_DIR}/flow_with_dict_input_with_variant")
        flow2.context = FlowContext(
            variant="${print_val.variant1}",
            connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
            overrides={"nodes.print_val.inputs.key": "a"},
        )
        flow_executor1 = FlowContextResolver.resolve(flow=flow1)
        flow_executor2 = FlowContextResolver.resolve(flow=flow2)
        assert flow_executor1 is flow_executor2

    def test_flow_cache_not_hit(self):
        with TemporaryDirectory() as tmp_dir:
            shutil.copytree(f"{FLOWS_DIR}/print_env_var", f"{tmp_dir}/print_env_var")
            flow_path = Path(f"{tmp_dir}/print_env_var")
            # load same file with different content will not hit cache
            flow1 = load_flow(flow_path)
            # update content
            _, flow_dag = load_flow_dag(flow_path)
            flow_dag["inputs"] = {"key": {"type": "string", "default": "key1"}}
            dump_flow_yaml_to_existing_path(flow_dag, flow_path)
            flow2 = load_flow(f"{tmp_dir}/print_env_var")
            flow_executor1 = FlowContextResolver.resolve(
                flow=flow1,
            )
            flow_executor2 = FlowContextResolver.resolve(
                flow=flow2,
            )
            assert flow_executor1 is not flow_executor2

    def test_flow_context_cache_not_hit(self):
        flow1 = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        flow1.context = FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k": "v"})}})
        flow2 = load_flow(f"{FLOWS_DIR}/flow_with_custom_connection")
        flow2.context = FlowContext(connections={"hello_node": {"connection": CustomConnection(secrets={"k2": "v"})}})
        flow_executor1 = FlowContextResolver.resolve(
            flow=flow1,
        )
        flow_executor2 = FlowContextResolver.resolve(
            flow=flow2,
        )
        assert flow_executor1 is not flow_executor2

        flow1 = load_flow(f"{FLOWS_DIR}/flow_with_dict_input_with_variant")
        flow1.context = FlowContext(
            variant="${print_val.variant1}",
            connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
            overrides={"nodes.print_val.inputs.key": "a"},
        )
        flow2 = load_flow(f"{FLOWS_DIR}/flow_with_dict_input_with_variant")
        flow2.context = FlowContext(
            variant="${print_val.variant1}",
            connections={"print_val": {"conn": CustomConnection(secrets={"k": "v"})}},
            overrides={"nodes.print_val.inputs.key": "b"},
        )
        flow_executor1 = FlowContextResolver.resolve(flow=flow1)
        flow_executor2 = FlowContextResolver.resolve(flow=flow2)
        assert flow_executor1 is not flow_executor2

    @pytest.mark.timeout(10)
    def test_flow_as_func_perf_test(self):
        # this test should not take long due to caching logic
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        for i in range(100):
            f(key="key")

    def test_flow_with_default_variant(self, azure_open_ai_connection):
        f = load_flow(f"{FLOWS_DIR}/web_classification_default_variant_no_llm_type")
        f.context = FlowContext(
            connections={
                "summarize_text_content": {"connection": azure_open_ai_connection},
            }
        )
        # function can successfully run with connection override
        f(url="https://www.youtube.com/watch?v=o5ZQyXaAv1g")

    def test_flow_with_connection_override(self, azure_open_ai_connection):
        f = load_flow(f"{FLOWS_DIR}/llm_tool_non_existing_connection")
        with pytest.raises(ConnectionNotFoundError):
            f(joke="joke")
        f.context = FlowContext(
            connections={
                "joke": {"connection": azure_open_ai_connection},
            }
        )
        # function can successfully run with connection override
        f(topic="joke")
        # This should work on subsequent call not just first
        f(topic="joke")
