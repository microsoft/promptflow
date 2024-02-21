import shutil
import tempfile
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from promptflow._sdk.entities import Run
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.azure import PFClient
from promptflow.exceptions import UserErrorException

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.unittest
class TestRunOperations:
    def test_download_run_with_invalid_workspace_datastore(self, pf: PFClient, mocker: MockerFixture):
        # test download with invalid workspace datastore
        mocker.patch.object(pf.runs, "_validate_for_run_download")
        mocker.patch.object(pf.runs, "_workspace_default_datastore", "test")
        with tempfile.TemporaryDirectory() as tmp_dir:
            with pytest.raises(UserErrorException, match="workspace default datastore is not supported"):
                pf.runs.download(run="fake_run_name", output=tmp_dir)

    def test_session_id_with_different_env(self, pf: PFClient):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            shutil.copytree(f"{FLOWS_DIR}/flow_with_environment", temp / "flow_with_environment")

            runtime, session_id1 = pf.runs._resolve_runtime(
                run=Run(
                    flow=temp / "flow_with_environment",
                    data=f"{DATAS_DIR}/env_var_names.jsonl",
                ),
                flow_path=temp / "flow_with_environment",
                runtime=None,
            )

            assert runtime == "automatic"

            # same flow will get same session id
            _, session_id2 = pf.runs._resolve_runtime(
                run=Run(
                    flow=temp / "flow_with_environment",
                    data=f"{DATAS_DIR}/env_var_names.jsonl",
                ),
                flow_path=temp / "flow_with_environment",
                runtime=None,
            )

            assert session_id2 == session_id1

            # update image
            flow_dict = load_yaml(temp / "flow_with_environment" / "flow.dag.yaml")
            flow_dict["environment"]["image"] = "python:3.9-slim"

            with open(temp / "flow_with_environment" / "flow.dag.yaml", "w", encoding="utf-8") as f:
                dump_yaml(flow_dict, f)
            _, session_id3 = pf.runs._resolve_runtime(
                run=Run(
                    flow=temp / "flow_with_environment",
                    data=f"{DATAS_DIR}/env_var_names.jsonl",
                ),
                flow_path=temp / "flow_with_environment",
                runtime=None,
            )

            assert session_id3 != session_id2

            # update requirements
            with open(temp / "flow_with_environment" / "requirements", "w", encoding="utf-8") as f:
                f.write("pandas==1.3.3")

            _, session_id4 = pf.runs._resolve_runtime(
                run=Run(
                    flow=temp / "flow_with_environment",
                    data=f"{DATAS_DIR}/env_var_names.jsonl",
                ),
                flow_path=temp / "flow_with_environment",
                runtime=None,
            )

            assert session_id3 != session_id4
