import mock
import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._load_functions import load_flow
from promptflow._sdk.entities._flows._flow_context_resolver import FlowContextResolver
from promptflow.core._connection_provider._workspace_connection_provider import WorkspaceConnectionProvider

FLOWS_DIR = PROMPTFLOW_ROOT / "tests" / "test_configs" / "flows"
DATAS_DIR = PROMPTFLOW_ROOT / "tests" / "test_configs" / "datas"


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
