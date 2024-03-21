from pathlib import Path

import mock
import pytest

from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._utils import get_local_connections_from_executable
from promptflow._sdk.operations._flow_context_resolver import FlowContextResolver
from promptflow._sdk.operations._local_azure_connection_operations import LocalAzureConnectionOperations

FLOWS_DIR = Path(__file__).parent.parent.parent / "test_configs" / "flows"
DATAS_DIR = Path(__file__).parent.parent.parent / "test_configs" / "datas"


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
        def assert_client(client, **kwargs):
            assert isinstance(client.connections, LocalAzureConnectionOperations)
            return get_local_connections_from_executable(client=client, **kwargs)

        flow = load_flow(source=f"{FLOWS_DIR}/web_classification")
        with mock.patch("promptflow._sdk._serving.flow_invoker.get_local_connections_from_executable", assert_client):
            FlowContextResolver.resolve(flow=flow)
