import os
import sys

import pytest

from promptflow._cli._pf_azure.entry import main


# TODO: move this to a shared utility module
def run_pf_command(*args, cwd=None):
    origin_argv, origin_cwd = sys.argv, os.path.abspath(os.curdir)
    try:
        sys.argv = ["pfazure"] + list(args)
        if cwd:
            os.chdir(cwd)
        main()
    finally:
        sys.argv = origin_argv
        os.chdir(origin_cwd)


@pytest.mark.e2etest
class TestCliWithAzure:
    # TODO: do we have such scenario? Or run_bulk shouldn't involve remote connections?
    @pytest.mark.skip(
        reason="Service principal doesn't have permission to list secrets for connections now"
    )
    def test_basic_flow_run_bulk_without_env(
        self,
        default_subscription_id: str,
        default_resource_group: str,
        workspace_with_acr_access: str,
        temp_output_dir: str,
    ) -> None:
        flows_dir = "./tests/test_configs/flows"

        run_pf_command(
            "run_bulk",
            "--input",
            "../../datas/webClassification3.jsonl",
            "-s",
            default_subscription_id,
            "-g",
            default_resource_group,
            "-w",
            workspace_with_acr_access,
            "--output",
            f"{temp_output_dir}/bulk_run_output",
            cwd=f"{flows_dir}/web_classification",
        )
        assert os.path.isdir(f"{temp_output_dir}/bulk_run_output")
