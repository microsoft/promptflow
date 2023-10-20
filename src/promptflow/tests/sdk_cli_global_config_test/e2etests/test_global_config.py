from pathlib import Path

import pytest

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

    def test_connection_operations(self, pf):
        connections = pf.connections.list()
        assert len(connections) > 0, f"No connection found. Provider: {pf._connection_provider}"
        # Assert create/update/delete not supported.
        with pytest.raises(NotImplementedError):
            pf.connections.create_or_update(connection=connections[0])

        with pytest.raises(NotImplementedError):
            pf.connections.delete(name="test_connection")
