import argparse
import sys
import pytest

from promptflow._cli._pf_azure._flow import add_parser_flow
from promptflow._cli._pf_azure._run import add_parser_run
from promptflow._cli._utils import _get_cli_activity_name


def get_cli_activity_name(cmd):
    sys.argv = list(cmd)[1:]
    parser = argparse.ArgumentParser(
        prog="pfazure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="pfazure: manage prompt flow assets in azure. Learn more: https://microsoft.github.io/promptflow.",
    )
    parser.add_argument(
        "-v", "--version", dest="version", action="store_true", help="show current CLI version and exit"
    )
    subparsers = parser.add_subparsers()
    add_parser_run(subparsers)
    add_parser_flow(subparsers)
    args = parser.parse_args(sys.argv)

    return _get_cli_activity_name(cli='pfazure', args=args)


@pytest.mark.unittest
class TestAzureCliTimeConsume:
    def test_pfazure_run_create(self, activity_name="pfazure.run.create"):
        assert get_cli_activity_name(
            cmd=(
                "pfazure",
                "run",
                "create",
                "--flow",
                "print_input_flow",
                "--data",
                "print_input_flow.jsonl"
            )) == activity_name

    def test_pfazure_run_update(self, activity_name="pfazure.run.update"):
        assert get_cli_activity_name(
            cmd=(
                "pfazure",
                "run",
                "update",
                "--name",
                "test_run",
                "--set",
                "display_name=test_run",
                "description='test_description'",
                "tags.key1=value1"
            )) == activity_name

    def test_run_restore(self, activity_name="pfazure.run.restore"):
        assert get_cli_activity_name(
            cmd=(
                "pfazure",
                "run",
                "restore",
                "--name",
                "test_run"
            )) == activity_name
