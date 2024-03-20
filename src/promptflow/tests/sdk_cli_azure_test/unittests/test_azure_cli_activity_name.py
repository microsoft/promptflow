import pytest

from promptflow._cli._utils import _get_cli_activity_name
from promptflow.azure._cli.entry import get_parser_args


def get_cli_activity_name(cmd):
    prog, args = get_parser_args(list(cmd)[1:])
    return _get_cli_activity_name(cli=prog, args=args)


@pytest.mark.unittest
class TestAzureCliTimeConsume:
    def test_pfazure_run_create(self, activity_name="pfazure.run.create"):
        assert (
            get_cli_activity_name(
                cmd=("pfazure", "run", "create", "--flow", "print_input_flow", "--data", "print_input_flow.jsonl")
            )
            == activity_name
        )

    def test_pfazure_run_update(self, activity_name="pfazure.run.update"):
        assert (
            get_cli_activity_name(
                cmd=(
                    "pfazure",
                    "run",
                    "update",
                    "--name",
                    "test_run",
                    "--set",
                    "display_name=test_run",
                    "description='test_description'",
                    "tags.key1=value1",
                )
            )
            == activity_name
        )

    def test_run_restore(self, activity_name="pfazure.run.restore"):
        assert get_cli_activity_name(cmd=("pfazure", "run", "restore", "--name", "test_run")) == activity_name
