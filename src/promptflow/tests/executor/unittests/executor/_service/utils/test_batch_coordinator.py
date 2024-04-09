import pytest

from promptflow.executor._service.utils.batch_coordinator import BatchCoordinator

from .....utils import get_flow_folder


@pytest.mark.unittest
class TestBatchCoordinator:
    @pytest.fixture(autouse=True)
    def resource_setup_and_teardown(self):
        # Setup code goes here

        # Yield to the test function
        yield

        # Teardown code goes here
        # Set _instance to None to avoid singleton pattern
        # Seems like BatchCoordinator.get_instance().close() can't be called if we don't call start first.
        BatchCoordinator._instance = None

    @pytest.mark.parametrize(
        "file_name, name_from_payload, expected_name",
        [
            ("yaml_with_name.yaml", "name_from_payload", "name_from_payload"),
            ("yaml_with_name.yaml", None, "name_from_yaml"),
            ("yaml_without_name.yaml", "name_from_payload", "name_from_payload"),
            ("yaml_without_name.yaml", None, "flow_name"),
        ],
    )
    @pytest.mark.asyncio
    async def test_executor_flow_name(self, file_name, name_from_payload, expected_name):
        flow_folder = get_flow_folder("flow_name")
        coordinator = BatchCoordinator(
            working_dir=flow_folder, flow_file=file_name, output_dir="", flow_name=name_from_payload
        )
        assert coordinator._flow_executor._flow.name == expected_name
