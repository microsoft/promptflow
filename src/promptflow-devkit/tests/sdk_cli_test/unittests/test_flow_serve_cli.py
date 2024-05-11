from pathlib import Path

import pytest
from mock import mock
from sdk_cli_test.e2etests.test_cli import run_pf_command

FLOWS_DIR = Path("./tests/test_configs/flows")
EAGER_FLOWS_DIR = Path("./tests/test_configs/eager_flows")


@pytest.mark.cli_test
@pytest.mark.unittest
class TestRun:
    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(EAGER_FLOWS_DIR / "simple_with_yaml", id="simple_with_yaml_dir"),
            pytest.param(FLOWS_DIR / "simple_hello_world", id="simple_hello_world_dir"),
        ],
    )
    def test_flow_serve(self, source: Path):
        with mock.patch("flask.app.Flask.run") as mock_run:
            run_pf_command(
                "flow",
                "serve",
                "--source",
                source.as_posix(),
                "--skip-open-browser",
            )
            mock_run.assert_called_once_with(port=8080, host="localhost")

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(EAGER_FLOWS_DIR / "simple_with_yaml" / "flow.flex.yaml", id="simple_with_yaml_file"),
            pytest.param(FLOWS_DIR / "simple_hello_world" / "flow.dag.yaml", id="simple_hello_world_file"),
        ],
    )
    def test_flow_serve_failed(self, source: Path, capsys):
        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "serve",
                "--source",
                source.as_posix(),
                "--skip-open-browser",
            )
        out, err = capsys.readouterr()
        assert (
            "pf.flow.serve failed with UserErrorException: Support directory `source` for Python flow only for now"
            in out
        )
