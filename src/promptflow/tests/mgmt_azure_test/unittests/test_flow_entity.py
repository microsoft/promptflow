# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from azure.ai.ml._utils._asset_utils import traverse_directory
from mock.mock import Mock

from promptflow.azure import BulkFlowRunInput
from promptflow.azure._load_functions import load_flow
from promptflow.azure.operations import FlowOperations
from promptflow.azure.operations._artifact_utilities import PromptflowIgnoreFile

tests_root_dir = Path(__file__).parent.parent.parent


@pytest.mark.unittest
class TestFlow:
    def test_variant_replace(self):
        bulk_flow_run_input = BulkFlowRunInput(
            data=tests_root_dir / "test_configs/flows/webClassification20.csv",
            variants=[Mock()],
            inputs_mapping={
                "question": "variants.output.url",
                "answer": "variants.output.answer",
                "context": "variants.output.evidence",
            },
        )
        assert bulk_flow_run_input.inputs_mapping == {
            "answer": "output.answer",
            "context": "output.evidence",
            "question": "output.url",
        }

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
        local_file = tests_root_dir / "test_configs/flows/meta_files/remote_fs.meta.yaml"

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
            ignore_file = PromptflowIgnoreFile(prompt_flow_path=flow_path)

            upload_paths = []
            for root, _, files in os.walk(flow_path, followlinks=True):
                upload_paths += list(
                    traverse_directory(root, files, Path(flow_path).resolve(), "", ignore_file=ignore_file)
                )
            flow_files = [item[1] for item in upload_paths]
            assert ".runs" not in flow_files
            assert ".runs/mockfile" not in flow_files
