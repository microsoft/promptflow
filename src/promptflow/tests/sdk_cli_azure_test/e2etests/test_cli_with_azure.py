# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import sys
import uuid
from typing import Callable

import pytest
from azure.ai.ml.entities import Data

from promptflow._cli._pf_azure.entry import main
from promptflow._sdk.entities import Run
from promptflow.azure import PFClient

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


# TODO: move this to a shared utility module
def run_pf_command(*args, pf, runtime, cwd=None):
    origin_argv, origin_cwd = sys.argv, os.path.abspath(os.curdir)
    try:
        sys.argv = (
            ["pfazure"]
            + list(args)
            + [
                "--runtime",
                runtime,
                "--subscription",
                pf._ml_client.subscription_id,
                "--resource-group",
                pf._ml_client.resource_group_name,
                "--workspace-name",
                pf._ml_client.workspace_name,
            ]
        )
        if cwd:
            os.chdir(cwd)
        main()
    finally:
        sys.argv = origin_argv
        os.chdir(origin_cwd)


@pytest.mark.e2etest
@pytest.mark.usefixtures("single_worker_thread_pool")
class TestCliWithAzure:
    def test_basic_flow_run_bulk_without_env(self, pf: PFClient, runtime: str, randstr: Callable[[str], str]):
        name = randstr("name")
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)

    @pytest.mark.skip("Custom tool pkg and promptprompt pkg with CustomStrongTypeConnection not installed on runtime.")
    def test_basic_flow_run_with_custom_strong_type_connection(self, pf, runtime) -> None:
        name = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/custom_strong_type_connection_basic_flow",
            "--data",
            f"{FLOWS_DIR}/custom_strong_type_connection_basic_flow/data.jsonl",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)

    def test_run_with_remote_data(self, pf: PFClient, runtime: str, remote_web_classification_data: Data):
        # run with arm id
        name = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            "web_classification",
            "--data",
            f"azureml:{remote_web_classification_data.id}",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
            cwd=f"{FLOWS_DIR}",
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)

        # run with name version
        name = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            "web_classification",
            "--data",
            f"azureml:{remote_web_classification_data.name}:{remote_web_classification_data.version}",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
            cwd=f"{FLOWS_DIR}",
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)
