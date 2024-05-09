# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT
from mock.mock import Mock
from sdk_cli_azure_test.conftest import EAGER_FLOWS_DIR, FLOWS_DIR

from promptflow import load_run
from promptflow._sdk._utilities.signature_utils import update_signatures
from promptflow._sdk._vendor import get_upload_files_from_folder
from promptflow._utils.flow_utils import load_flow_dag
from promptflow.azure._constants._flow import ENVIRONMENT, PYTHON_REQUIREMENTS_TXT
from promptflow.azure._entities._flow import Flow
from promptflow.core._errors import GenerateFlowMetaJsonError
from promptflow.exceptions import UserErrorException, ValidationException

RUNS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/runs"


def load_flow(source):
    from promptflow.azure._load_functions import load_flow

    return load_flow(source=source)


@pytest.mark.unittest
class TestFlow:
    @pytest.mark.skip(reason="TODO: add back when we bring back meta.yaml")
    def test_load_flow(self):

        local_file = FLOWS_DIR / "meta_files/flow.meta.yaml"

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
        from promptflow.azure.operations._flow_operations import FlowOperations

        local_file = FLOWS_DIR / "meta_files/remote_fs.meta.yaml"

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
        local_file = FLOWS_DIR / "web_classification"
        with tempfile.TemporaryDirectory() as temp:
            flow_path = Path(temp) / "flow"
            shutil.copytree(local_file, flow_path)
            assert (Path(temp) / "flow/.promptflow/flow.tools.json").exists()

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
            # assert that .runs/mock.file are ignored
            assert ".runs/mock.file" not in flow_files
            # Web classification may be executed and include flow.detail.json, flow.logs, flow.outputs.json
            assert all(
                file in flow_files
                for file in [
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
            )

    def test_load_yaml_run_with_resources(self):
        source = f"{RUNS_DIR}/sample_bulk_run_with_resources.yaml"
        run = load_run(source=source, params_override=[{"name": str(uuid.uuid4())}])
        assert dict(run._resources) == {"instance_type": "Standard_D2"}

    def test_load_yaml_run_with_resources_unsupported_field(self):
        source = f"{RUNS_DIR}/sample_bulk_run_with_idle_time.yaml"
        with pytest.raises(ValidationException) as e:
            load_run(source=source, params_override=[{"name": str(uuid.uuid4())}])
        assert "Unknown field" in str(e.value)

    def test_flow_with_additional_includes(self):
        flow_folder = FLOWS_DIR / "web_classification_with_additional_include"
        flow = load_flow(source=flow_folder)

        with flow._build_code() as code:
            assert code is not None
            _, temp_flow = load_flow_dag(code.path)
            assert "additional_includes" not in temp_flow
            upload_paths = get_upload_files_from_folder(
                path=code.path,
                ignore_file=code._ignore_file,
            )
            flow_files = list(sorted([item[1] for item in upload_paths]))
            target_additional_includes = [
                "convert_to_dict.py",
                "fetch_text_content_from_url.py",
                "summarize_text_content.jinja2",
                "external_files/convert_to_dict.py",
                "external_files/fetch_text_content_from_url.py",
                "external_files/summarize_text_content.jinja2",
            ]

            # assert all additional includes are included
            for file in target_additional_includes:
                assert file in flow_files

    def test_flow_with_ignore_file(self):
        flow_folder = FLOWS_DIR / "flow_with_ignore_file"
        flow = load_flow(source=flow_folder)

        with flow._build_code() as code:
            assert code is not None
            upload_paths = get_upload_files_from_folder(
                path=code.path,
                ignore_file=code._ignore_file,
            )
            flow_files = list(sorted([item[1] for item in upload_paths]))
            assert len(flow_files) > 0
            target_ignored_files = ["ignored_folder/1.txt", "random.ignored"]

            # assert all ignored files are ignored
            for file in target_ignored_files:
                assert file not in flow_files

    def test_resolve_requirements(self):
        flow_dag = {}

        # Test when requirements.txt does not exist
        assert not Flow._resolve_requirements(flow_path=FLOWS_DIR / "flow_with_ignore_file", flow_dag=flow_dag)

        # Test when requirements.txt exists but already added to flow_dag
        flow_dag[ENVIRONMENT] = {PYTHON_REQUIREMENTS_TXT: "another_requirements.txt"}
        assert not Flow._resolve_requirements(flow_path=FLOWS_DIR / "flow_with_requirements_txt", flow_dag=flow_dag)

        # Test when requirements.txt exists and not added to flow_dag
        flow_dag = {}
        assert Flow._resolve_requirements(flow_path=FLOWS_DIR / "flow_with_requirements_txt", flow_dag=flow_dag)

    def test_resolve_requirements_for_flow(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            # flow without environment section
            flow_folder = FLOWS_DIR / "flow_with_requirements_txt"
            shutil.copytree(flow_folder, temp / "flow_with_requirements_txt")
            flow_folder = temp / "flow_with_requirements_txt"
            flow = load_flow(source=flow_folder)
            with flow._build_code():
                _, flow_dag = load_flow_dag(flow_path=flow_folder)
                assert flow_dag[ENVIRONMENT] == {"python_requirements_txt": "requirements.txt"}

            _, flow_dag = load_flow_dag(flow_path=flow_folder)
            assert ENVIRONMENT not in flow_dag

            # flow with environment section
            flow_folder = FLOWS_DIR / "flow_with_requirements_txt_and_env"
            shutil.copytree(flow_folder, temp / "flow_with_requirements_txt_and_env")
            flow_folder = temp / "flow_with_requirements_txt_and_env"
            flow = load_flow(source=flow_folder)
            with flow._build_code():
                _, flow_dag = load_flow_dag(flow_path=flow_folder)
                assert flow_dag[ENVIRONMENT] == {
                    "image": "python:3.8-slim",
                    "python_requirements_txt": "requirements.txt",
                }

            _, flow_dag = load_flow_dag(flow_path=flow_folder)
            assert flow_dag[ENVIRONMENT] == {"image": "python:3.8-slim"}

    def test_flow_resolve_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            # flow without env
            shutil.copytree(FLOWS_DIR / "hello-world", temp / "hello-world")
            flow = load_flow(source=temp / "hello-world")
            with flow._build_code():
                assert flow._environment == {}

            # flow with requirements
            shutil.copytree(FLOWS_DIR / "flow_with_requirements_txt", temp / "flow_with_requirements_txt")
            flow = load_flow(source=temp / "flow_with_requirements_txt")
            with flow._build_code():
                assert flow._environment == {"python_requirements_txt": ["langchain"]}

            shutil.copytree(
                FLOWS_DIR / "flow_with_requirements_txt_and_env", temp / "flow_with_requirements_txt_and_env"
            )
            flow = load_flow(source=temp / "flow_with_requirements_txt_and_env")
            with flow._build_code():
                assert flow._environment == {"image": "python:3.8-slim", "python_requirements_txt": ["langchain"]}

            # flow with requirements in additional includes
            flow = load_flow(source=FLOWS_DIR / "flow_with_additional_include_req")
            with flow._build_code():
                assert flow._environment == {"python_requirements_txt": ["tensorflow"]}

    @pytest.mark.parametrize(
        "exception_type, data, error_message",
        [
            (
                GenerateFlowMetaJsonError,
                {"entry": "invalid_call:MyFlow"},
                "The input 'func_input' is of a complex python type",
            ),
            (
                GenerateFlowMetaJsonError,
                {"entry": "invalid_init:MyFlow"},
                "The input 'obj_input' is of a complex python type",
            ),
            (
                GenerateFlowMetaJsonError,
                {"entry": "invalid_output:MyFlow"},
                "The output 'obj_input' is of a complex python type",
            ),
            (
                UserErrorException,
                {
                    "entry": "simple_callable_class:MyFlow",
                    "init": {
                        "obj_input": {
                            "type": "Object",
                        }
                    },
                },
                "'init.obj_input.type': 'Must be one of",
            ),
            (
                UserErrorException,
                {
                    "entry": "simple_callable_class:MyFlow",
                    "inputs": {
                        "func_input": {
                            "type": "Object",
                        }
                    },
                },
                "'inputs.func_input.type': 'Must be one of",
            ),
            (
                UserErrorException,
                {
                    "entry": "simple_callable_class:MyFlow",
                    "outputs": {
                        "func_input": {
                            "type": "Object",
                        }
                    },
                },
                "Provided signature of outputs does not match the entry",
            ),
        ],
    )
    def test_flex_flow_run_unsupported_types(self, exception_type, data, error_message):
        with pytest.raises(exception_type) as e:
            update_signatures(
                code=Path(f"{EAGER_FLOWS_DIR}/invalid_illegal_input_type"),
                data=data,
            )
        assert error_message in str(e.value)

    @pytest.mark.parametrize(
        "code, data, expected_data",
        [
            (
                Path(f"{EAGER_FLOWS_DIR}/basic_model_config"),
                {
                    "entry": "class_with_model_config:MyFlow",
                },
                {
                    "entry": "class_with_model_config:MyFlow",
                    "init": {
                        "azure_open_ai_model_config": {"type": "AzureOpenAIModelConfiguration"},
                        "open_ai_model_config": {"type": "OpenAIModelConfiguration"},
                    },
                    "inputs": {"func_input": {"type": "string"}},
                    "outputs": {
                        "func_input": {"type": "string"},
                        "obj_id": {"type": "string"},
                        "obj_input": {"type": "string"},
                    },
                },
            ),
            (
                Path(f"{EAGER_FLOWS_DIR}/code_yaml_signature_merge"),
                {"entry": "partial_signatures:MyFlow"},
                {
                    "entry": "partial_signatures:MyFlow",
                    "init": {
                        "obj_input1": {"type": "string"},
                        "obj_input2": {"type": "bool"},
                        "obj_input3": {"type": "object"},
                    },
                    "inputs": {
                        "func_input1": {"type": "string"},
                        "func_input2": {"type": "int"},
                        "func_input3": {"type": "object"},
                    },
                    "outputs": {"output": {"type": "string"}},
                },
            ),
            (
                Path(f"{EAGER_FLOWS_DIR}/code_yaml_signature_merge"),
                {
                    "entry": "partial_signatures:MyFlow",
                    "init": {
                        "obj_input1": {"type": "string"},
                        "obj_input2": {"type": "bool"},
                        "obj_input3": {"type": "string"},
                    },
                    "inputs": {
                        "func_input1": {"type": "string"},
                        "func_input2": {"type": "int"},
                        "func_input3": {"type": "string"},
                    },
                    "outputs": {"output": {"type": "string"}},
                },
                {
                    "entry": "partial_signatures:MyFlow",
                    "init": {
                        "obj_input1": {"type": "string"},
                        "obj_input2": {"type": "bool"},
                        "obj_input3": {"type": "string"},
                    },
                    "inputs": {
                        "func_input1": {"type": "string"},
                        "func_input2": {"type": "int"},
                        "func_input3": {"type": "string"},
                    },
                    "outputs": {"output": {"type": "string"}},
                },
            ),
        ],
    )
    def test_update_signature(self, code, data, expected_data):
        update_signatures(
            code=code,
            data=data,
        )
        assert data == expected_data
