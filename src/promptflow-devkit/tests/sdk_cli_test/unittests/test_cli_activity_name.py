import pytest

from promptflow._cli._pf.entry import get_parser_args
from promptflow._cli._utils import _get_cli_activity_name


def get_cli_activity_name(cmd):
    prog, args = get_parser_args(list(cmd)[1:])
    return _get_cli_activity_name(cli=prog, args=args)


@pytest.mark.unittest
class TestCliTimeConsume:
    def test_pf_run_create(self, activity_name="pf.run.create") -> None:
        assert (
            get_cli_activity_name(
                cmd=(
                    "pf",
                    "run",
                    "create",
                    "--flow",
                    "print_input_flow",
                    "--data",
                    "print_input_flow.jsonl",
                )
            )
            == activity_name
        )

    def test_pf_run_update(self, activity_name="pf.run.update") -> None:
        assert (
            get_cli_activity_name(
                cmd=("pf", "run", "update", "--name", "test_name", "--set", "description=test pf run update")
            )
            == activity_name
        )

    def test_pf_flow_test(self, activity_name="pf.flow.test"):
        assert (
            get_cli_activity_name(
                cmd=(
                    "pf",
                    "flow",
                    "test",
                    "--flow",
                    "print_input_flow",
                    "--inputs",
                    "text=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
                )
            )
            == activity_name
        )

    def test_pf_flow_build(self, activity_name="pf.flow.build"):
        assert (
            get_cli_activity_name(
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
                )
            )
            == activity_name
        )

    def test_pf_connection_create(self, activity_name="pf.connection.create"):
        assert (
            get_cli_activity_name(
                cmd=(
                    "pf",
                    "connection",
                    "create",
                    "--file",
                    "azure_openai_connection.yaml",
                    "--name",
                    "test_name",
                )
            )
            == activity_name
        )

    def test_pf_connection_list(self, activity_name="pf.connection.list"):
        assert get_cli_activity_name(cmd=("pf", "connection", "list")) == activity_name
