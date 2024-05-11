import pytest
from _constants import PROMPTFLOW_ROOT
from sdk_cli_test.e2etests.test_cli import run_pf_command

from promptflow._sdk._constants import SCRUBBED_VALUE

CONNECTIONS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/connections"


@pytest.mark.usefixtures("global_config")
@pytest.mark.e2etest
class TestConnectionCli:
    @pytest.mark.parametrize(
        "file_name, expected",
        [
            (
                "azure_openai_connection.yaml",
                {
                    "module": "promptflow.connections",
                    "type": "azure_open_ai",
                    "api_type": "azure",
                    "api_version": "2023-07-01-preview",
                    "api_key": SCRUBBED_VALUE,
                    "api_base": "aoai-api-endpoint",
                    "resource_id": "mock_id",
                },
            )
        ],
    )
    def test_connection_create_update(self, file_name, expected, capfd):
        with pytest.raises(NotImplementedError) as e:
            run_pf_command("connection", "create", "--file", f"{CONNECTIONS_DIR}/{file_name}")
        assert "not supported in promptflow" in str(e)
