import os
import sys

import pytest
from azure.ai.ml import MLClient
from azure.identity import AzureCliCredential, DefaultAzureCredential

from promptflow._cli.pf_azure.pf_azure import main
from promptflow.azure import PFClient, configure
from promptflow.utils.utils import is_in_ci_pipeline


@pytest.fixture(scope="session")
def remote_client() -> PFClient:
    cred = DefaultAzureCredential()
    if is_in_ci_pipeline():
        cred = AzureCliCredential()
    client = MLClient(
        credential=cred,
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-eastus",
    )
    configure(client=client)
    return PFClient(client)


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
    @pytest.mark.skip(reason="Service principal doesn't have permission to list secrets for connections now")
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
            "../webClassification3.jsonl",
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
