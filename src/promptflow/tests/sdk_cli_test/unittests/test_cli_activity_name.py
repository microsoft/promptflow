import argparse
import sys

import pytest

from promptflow._cli._pf._config import add_config_parser
from promptflow._cli._pf._connection import add_connection_parser
from promptflow._cli._pf._flow import add_flow_parser
from promptflow._cli._pf._run import add_run_parser
from promptflow._cli._pf._tool import add_tool_parser
from promptflow._cli._utils import _get_cli_activity_name


def get_cli_activity_name(cmd):
    sys.argv = list(cmd)[1:]
    parser = argparse.ArgumentParser(
        prog="pf",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="pf: manage prompt flow assets. Learn more: https://microsoft.github.io/promptflow.",
    )
    parser.add_argument(
        "-v", "--version", dest="version", action="store_true", help="show current CLI version and exit"
    )
    subparsers = parser.add_subparsers()
    add_flow_parser(subparsers)
    add_connection_parser(subparsers)
    add_run_parser(subparsers)
    add_config_parser(subparsers)
    add_tool_parser(subparsers)

    args = parser.parse_args(sys.argv)
    return _get_cli_activity_name(cli='pf', args=args)


@pytest.mark.unittest
class TestCliTimeConsume:
    def test_pf_run_create(self, activity_name="pf.run.create") -> None:
        assert get_cli_activity_name(
            cmd=(
                "pf",
                "run",
                "create",
                "--flow",
                "print_input_flow",
                "--data",
                "print_input_flow.jsonl",
            )) == activity_name

    def test_pf_run_update(self, activity_name="pf.run.update") -> None:
        assert get_cli_activity_name(
            cmd=(
                "pf",
                "run",
                "update",
                "--name",
                "test_name",
                "--set",
                "description=test pf run update"
            )) == activity_name

    def test_pf_flow_test(self, activity_name="pf.flow.test"):
        assert get_cli_activity_name(
            cmd=(
                "pf",
                "flow",
                "test",
                "--flow",
                "print_input_flow",
                "--inputs",
                "text=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
            )) == activity_name

    def test_pf_flow_build(self, activity_name="pf.flow.build"):
        assert get_cli_activity_name(
            cmd=(
                "pf",
                "flow",
                "build",
                "--source",
                "print_input_flow/flow.dag.yaml",
                "--output",
                "./",
                "--format",
                "docker",
            )) == activity_name

    def test_pf_connection_create(self, activity_name="pf.connection.create"):
        assert get_cli_activity_name(
            cmd=(
                "pf",
                "connection",
                "create",
                "--file",
                "azure_openai_connection.yaml",
                "--name",
                "test_name",
            )) == activity_name

    def test_pf_connection_list(self, activity_name="pf.connection.list"):
        assert get_cli_activity_name(cmd=("pf", "connection", "list")) == activity_name
