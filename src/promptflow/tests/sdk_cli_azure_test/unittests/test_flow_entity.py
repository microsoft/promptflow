# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from mock.mock import Mock

from promptflow._sdk._load_functions import load_run
from promptflow._sdk._vendor import get_upload_files_from_folder
from promptflow.azure._load_functions import load_flow
from promptflow.azure.operations._flow_opearations import FlowOperations

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."
FLOWS_DIR = Path("./tests/test_configs/flows")
RUNS_DIR = Path("./tests/test_configs/runs")

tests_root_dir = Path(__file__).parent.parent.parent


@pytest.mark.unittest
class TestFlow:
    @pytest.mark.skip(reason="TODO: add back when we bring back meta.yaml")
    def test_load_flow(self):
        local_file = tests_root_dir / "test_configs/flows/meta_files/flow.meta.yaml"

        flow = load_flow(source=local_file)

        assert flow._to_dict() == {
            "name": "web_classificiation_flow_3",
            "description": "Create flows that use large language models to classify URLs into multiple categories.",
            "display_name": "Web Classification",
            "type": "default",
            "path": "./flow.dag.yaml",
        }
        rest_dict = flow._to_rest_object().as_dict()
        assert rest_dict == {
            "description": "Create flows that use large language models to classify URLs into multiple categories.",
            "flow_name": "Web Classification",
            "flow_run_settings": {},
            "flow_type": "default",
            "is_archived": True,
            "flow_definition_file_path": "./flow.dag.yaml",
        }

    @pytest.mark.skip(reason="TODO: add back when we bring back meta.yaml")
    def test_load_flow_from_remote_storage(self):
        local_file = (
            tests_root_dir / "test_configs/flows/meta_files/remote_fs.meta.yaml"
        )

        flow = load_flow(source=local_file)

        assert flow._to_dict() == {
            "name": "classification_accuracy_eval",
            "path": "azureml://datastores/workspaceworkingdirectory/paths/Users/wanhan/my_flow_snapshot/flow.dag.yaml",
            "type": "evaluation",
        }

        FlowOperations._try_resolve_code_for_flow(flow, Mock())
        rest_dict = flow._to_rest_object().as_dict()

        assert rest_dict == {
            "flow_definition_file_path": "Users/wanhan/my_flow_snapshot/flow.dag.yaml",
            "flow_run_settings": {},
            "flow_type": "evaluation",
            "is_archived": True,
        }

    def test_ignore_files_in_flow(self):
        local_file = tests_root_dir / "test_configs/flows/web_classification"
        with tempfile.TemporaryDirectory() as temp:
            flow_path = Path(temp) / "flow"
            shutil.copytree(local_file, flow_path)

            (Path(flow_path) / ".runs").mkdir(parents=True)
            (Path(flow_path) / ".runs" / "mock.file").touch()

            flow = load_flow(source=flow_path)
            with flow._build_code() as code:
                assert code is not None
                upload_paths = get_upload_files_from_folder(
                    path=code.path,
                    ignore_file=code._ignore_file,
                )

            flow_files = list(sorted([item[1] for item in upload_paths]))
            # TODO: should we ignore __pycache__ by default?
            # assert that .runs/mock.file are ignored
            assert flow_files == [
                ".promptflow/flow.tools.json",
                "classify_with_llm.jinja2",
                "convert_to_dict.py",
                "fetch_text_content_from_url.py",
                "fetch_text_content_from_url_input.jsonl",
                "flow.dag.yaml",
                "prepare_examples.py",
                "samples.json",
                "summarize_text_content.jinja2",
                "summarize_text_content__variant_1.jinja2",
                "webClassification20.csv",
            ]

    def test_load_yaml_run_with_resources(self):
        source = f"{RUNS_DIR}/sample_bulk_run_with_resources.yaml"
        run = load_run(source=source, params_override=[{"name": str(uuid.uuid4())}])
        assert run._resources["instance_type"] == "Standard_DSV2"
        assert run._resources["idle_time_before_shutdown_minutes"] == 60
