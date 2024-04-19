import os
import os.path
from typing import Callable

import pytest

from promptflow.azure import PFClient


def get_repo_base_path():
    return os.getenv("CSHARP_REPO_BASE_PATH", None)


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.cli_test
@pytest.mark.e2etest
@pytest.mark.skipif(get_repo_base_path() is None, reason="available locally only before csharp support go public")
class TestCSharpCli:
    def test_eager_flow_run_without_yaml(self, pf: PFClient, randstr: Callable[[str], str]):
        pf.run(
            flow=f"{get_repo_base_path()}\\src\\PromptflowCSharp\\Sample\\Basic\\bin\\Debug\\net6.0",
        )
