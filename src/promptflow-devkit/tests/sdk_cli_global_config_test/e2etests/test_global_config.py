import mock
import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._load_functions import load_flow
from promptflow._sdk.entities._flows._flow_context_resolver import FlowContextResolver
from promptflow.contracts.run_info import Status
from promptflow.core import Prompty
from promptflow.core._connection_provider._workspace_connection_provider import WorkspaceConnectionProvider
from promptflow.executor._script_executor import ScriptExecutor

TEST_CONFIG_DIR = PROMPTFLOW_ROOT / "tests" / "test_configs"
FLOWS_DIR = TEST_CONFIG_DIR / "flows"
DATAS_DIR = TEST_CONFIG_DIR / "datas"
PROMPTY_DIR = TEST_CONFIG_DIR / "prompty"
EAGER_FLOW_ROOT = TEST_CONFIG_DIR / "eager_flows"


@pytest.mark.usefixtures("global_config")
@pytest.mark.e2etest
class TestGlobalConfig:
    def test_basic_flow_bulk_run(self, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        assert run.status == "Completed"
        # Test repeated execute flow run
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        assert run.status == "Completed"

    def test_connection_operations(self, pf) -> None:
        connections = pf.connections.list()
        assert len(connections) > 0, f"No connection found. Provider: {pf._connection_provider}"
        # Assert create/update/delete not supported.
        with pytest.raises(NotImplementedError):
            pf.connections.create_or_update(connection=connections[0])

        with pytest.raises(NotImplementedError):
            pf.connections.delete(name="test_connection")

    def test_flow_as_func(self):
        # Assert flow as func use azure provider, honor global connection config
        def assert_client(mock_self, provider, **kwargs):
            assert isinstance(provider, WorkspaceConnectionProvider)
            return {
                "azure_open_ai_connection": provider.get(
                    name="azure_open_ai_connection"
                )._to_execution_connection_dict()
            }

        flow = load_flow(source=f"{FLOWS_DIR}/web_classification")
        with mock.patch("promptflow.core._serving.flow_invoker.FlowInvoker.resolve_connections", assert_client):
            FlowContextResolver.resolve(flow=flow)

    def test_prompty_callable(self, pf):
        # Test prompty callable with global config ws connection
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

    @pytest.mark.skip("To investigate - IndexError: list index out of range")
    def test_flex_flow_run_with_openai_chat(self, pf):
        # Test flex flow run successfully with global config ws connection
        flow_file = EAGER_FLOW_ROOT / "callable_class_with_openai" / "flow.flex.yaml"
        pf._ensure_connection_provider()
        executor = ScriptExecutor(flow_file=flow_file, init_kwargs={"connection": "azure_open_ai_connection"})
        line_result = executor.exec_line(inputs={"question": "Hello", "stream": False}, index=0)
        assert line_result.run_info.status == Status.Completed, line_result.run_info.error
        token_names = ["prompt_tokens", "completion_tokens", "total_tokens"]
        for token_name in token_names:
            assert token_name in line_result.run_info.api_calls[0]["children"][0]["system_metrics"]
