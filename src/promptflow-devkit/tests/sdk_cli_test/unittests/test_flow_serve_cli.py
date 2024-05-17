import os
import sys
from pathlib import Path

import pytest
from mock import mock

from promptflow._cli._pf.entry import main

FLOWS_DIR = Path("./tests/test_configs/flows")
EAGER_FLOWS_DIR = Path("./tests/test_configs/eager_flows")
PROMPTY_DIR = Path("./tests/test_configs/prompty")


# TODO: move this to a shared utility module
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


@pytest.mark.cli_test
@pytest.mark.unittest
class TestRun:
    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(EAGER_FLOWS_DIR / "simple_with_yaml", id="simple_flex_dir"),
            pytest.param(FLOWS_DIR / "simple_hello_world", id="simple_dag_dir"),
            pytest.param(PROMPTY_DIR / "single_prompty", id="simple_prompty_dir"),
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
        with mock.patch("uvicorn.run") as mock_run:
            run_pf_command(
                "flow",
                "serve",
                "--source",
                source.as_posix(),
                "--skip-open-browser",
                "--engine",
                "fastapi",
            )
            mock_run.assert_called_once()

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

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(EAGER_FLOWS_DIR / "simple_with_yaml", id="simple_with_yaml_file"),
            pytest.param(FLOWS_DIR / "simple_hello_world", id="simple_hello_world_file"),
        ],
    )
    def test_flow_serve_invalid_engine(self, source: Path, capsys):
        invalid_engine = "invalid_engine"
        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "serve",
                "--source",
                source.as_posix(),
                "--skip-open-browser",
                "--engine",
                invalid_engine,
            )
        out, err = capsys.readouterr()
        assert f"Unsupported engine {invalid_engine} for Python flow, only support 'flask' and 'fastapi'." in out
