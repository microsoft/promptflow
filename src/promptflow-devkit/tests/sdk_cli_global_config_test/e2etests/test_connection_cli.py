import os
import sys

import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._cli._pf.entry import main
from promptflow._sdk._constants import SCRUBBED_VALUE

CONNECTIONS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/connections"


def run_pf_command(*args, cwd=None):
    """Run a pf command with the given arguments and working directory.

    There have been some unknown issues in using subprocess on CI, so we use this function instead, which will also
    provide better debugging experience.
    """
    origin_argv, origin_cwd = sys.argv, os.path.abspath(os.curdir)
    try:
        sys.argv = ["pf"] + list(args)
        if cwd:
            os.chdir(cwd)
        main()
    finally:
        sys.argv = origin_argv
        os.chdir(origin_cwd)


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
