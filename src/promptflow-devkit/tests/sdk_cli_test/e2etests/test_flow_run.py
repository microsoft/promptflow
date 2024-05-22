import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from _constants import PROMPTFLOW_ROOT
from marshmallow import ValidationError
from pytest_mock import MockerFixture

from promptflow._constants import PROMPTFLOW_CONNECTIONS, FlowType
from promptflow._sdk._constants import (
    FLOW_DIRECTORY_MACRO_IN_CONFIG,
    PROMPT_FLOW_DIR_NAME,
    FlowRunProperties,
    LocalStorageFilenames,
    RunStatus,
)
from promptflow._sdk._errors import (
    ConnectionNotFoundError,
    InvalidFlowError,
    InvalidRunError,
    InvalidRunStatusError,
    RunExistsError,
    RunNotFoundError,
)
from promptflow._sdk._load_functions import load_flow, load_run
from promptflow._sdk._orchestrator.utils import SubmitterHelper
from promptflow._sdk._run_functions import create_yaml_run
from promptflow._sdk._utilities.general_utils import _get_additional_includes
from promptflow._sdk._utilities.tracing_utils import _parse_otel_span_status_code
from promptflow._sdk.entities import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow._utils.yaml_utils import load_yaml
from promptflow.client import PFClient
from promptflow.connections import AzureOpenAIConnection
from promptflow.core import AzureOpenAIModelConfiguration, OpenAIModelConfiguration
from promptflow.exceptions import UserErrorException

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
CONNECTION_FILE = (PROMPTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/flows"
EAGER_FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/eager_flows"
RUNS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/runs"
DATAS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/datas"


def my_entry(input1: str):
    return input1


async def my_async_entry(input2: str):
    return input2


def create_run_against_multi_line_data(client) -> Run:
    return client.run(
        flow=f"{FLOWS_DIR}/web_classification",
        data=f"{DATAS_DIR}/webClassification3.jsonl",
        column_mapping={"url": "${data.url}"},
    )


def create_run_against_multi_line_data_without_llm(client: PFClient) -> Run:
    return client.run(
        flow=f"{FLOWS_DIR}/print_env_var",
        data=f"{DATAS_DIR}/env_var_names.jsonl",
    )


def create_run_against_run(client, run: Run) -> Run:
    return client.run(
        flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
        data=f"{DATAS_DIR}/webClassification3.jsonl",
        run=run.name,
        column_mapping={
            "groundtruth": "${data.answer}",
            "prediction": "${run.outputs.category}",
            "variant_id": "${data.variant_id}",
        },
    )


def assert_run_with_invalid_column_mapping(client: PFClient, run: Run) -> None:
    assert run.status == RunStatus.FAILED

    with pytest.raises(InvalidRunStatusError):
        client.stream(run.name)

    local_storage = LocalStorageOperations(run)
    assert os.path.exists(local_storage._exception_path)

    exception = local_storage.load_exception()
    assert "The input for batch run is incorrect. Couldn't find these mapping relations" in exception["message"]
    assert exception["code"] == "UserError"
    assert exception["innerError"]["innerError"]["code"] == "BulkRunException"


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowRun:
    def test_basic_flow_bulk_run(self, azure_open_ai_connection: AzureOpenAIConnection, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        # Test repeated execute flow run
        pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)

        pf.run(flow=f"{FLOWS_DIR}/web_classification_v1", data=data_path)
        pf.run(flow=f"{FLOWS_DIR}/web_classification_v2", data=data_path)

        # TODO: check details
        # df = pf.show_details(baseline, v1, v2)

    def test_basic_run_bulk(self, azure_open_ai_connection: AzureOpenAIConnection, local_client, pf):
        column_mapping = {"url": "${data.url}"}
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping=column_mapping,
        )
        local_storage = LocalStorageOperations(result)
        detail = local_storage.load_detail()
        tuning_node = next((x for x in detail["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used default variant config
        assert tuning_node["inputs"]["temperature"] == 0.3
        assert "variant_0" in result.name

        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"
        assert run.column_mapping == column_mapping
        # write to user_dir/.promptflow/.runs
        assert ".promptflow" in run.properties["output_path"]

    def test_local_storage_delete(self, pf):
        result = pf.run(flow=f"{FLOWS_DIR}/print_env_var", data=f"{DATAS_DIR}/env_var_names.jsonl")
        local_storage = LocalStorageOperations(result)
        local_storage.delete()
        assert not os.path.exists(local_storage._outputs_path)

    def test_flow_run_delete(self, pf):
        result = pf.run(flow=f"{FLOWS_DIR}/print_env_var", data=f"{DATAS_DIR}/env_var_names.jsonl")
        local_storage = LocalStorageOperations(result)
        output_path = local_storage.path

        # delete new created run by name
        pf.runs.delete(result.name)

        # check folders and dbs are deleted
        assert not os.path.exists(output_path)

        from promptflow._sdk._orm import RunInfo as ORMRun

        pytest.raises(RunNotFoundError, lambda: ORMRun.get(result.name))
        pytest.raises(RunNotFoundError, lambda: pf.runs.get(result.name))

    def test_flow_run_delete_fake_id_raise(self, pf: PFClient):
        run = "fake_run_id"

        # delete new created run by name
        pytest.raises(RunNotFoundError, lambda: pf.runs.delete(name=run))

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows doesn't support chmod, just test permission errors")
    def test_flow_run_delete_invalid_permission_raise(self, pf: PFClient):
        result = pf.run(flow=f"{FLOWS_DIR}/print_env_var", data=f"{DATAS_DIR}/env_var_names.jsonl")
        local_storage = LocalStorageOperations(result)
        output_path = local_storage.path
        os.chmod(output_path, 0o555)

        # delete new created run by name
        pytest.raises(InvalidRunError, lambda: pf.runs.delete(name=result.name))

        # Change folder permission back
        os.chmod(output_path, 0o755)
        pf.runs.delete(name=result.name)
        assert not os.path.exists(output_path)

    def test_visualize_run_with_referenced_run_deleted(self, pf: PFClient):
        run_id = str(uuid.uuid4())
        run = load_run(
            source=f"{RUNS_DIR}/sample_bulk_run.yaml",
            params_override=[{"name": run_id}],
        )
        run_a = pf.runs.create_or_update(run=run)
        local_storage_a = LocalStorageOperations(run_a)
        output_path_a = local_storage_a.path

        run = load_run(source=f"{RUNS_DIR}/sample_eval_run.yaml", params_override=[{"run": run_id}])
        run_b = pf.runs.create_or_update(run=run)
        local_storage_b = LocalStorageOperations(run_b)
        output_path_b = local_storage_b.path

        pf.runs.delete(run_a.name)
        assert not os.path.exists(output_path_a)
        assert os.path.exists(output_path_b)

        # visualize doesn't raise error
        pf.runs.visualize(run_b.name)

    def test_basic_flow_with_variant(self, azure_open_ai_connection: AzureOpenAIConnection, local_client, pf) -> None:
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
        )
        local_storage = LocalStorageOperations(result)
        detail = local_storage.load_detail()
        tuning_node = next((x for x in detail["node_runs"] if x["node"] == "summarize_text_content"), None)
        assert "variant_0" in result.name

        # used variant_0 config
        assert tuning_node["inputs"]["temperature"] == 0.2
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_1}",
        )
        local_storage = LocalStorageOperations(result)
        detail = local_storage.load_detail()
        tuning_node = next((x for x in detail["node_runs"] if x["node"] == "summarize_text_content"), None)
        assert "variant_1" in result.name
        # used variant_1 config
        assert tuning_node["inputs"]["temperature"] == 0.3

    def test_run_bulk_error(self, pf):
        # path not exist
        with pytest.raises(UserErrorException) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/not_exist",
                data=f"{DATAS_DIR}/webClassification3.jsonl",
                column_mapping={"question": "${data.question}", "context": "${data.context}"},
                variant="${summarize_text_content.variant_0}",
            )
        assert "not exist" in str(e.value)

        # tuning_node not exist
        with pytest.raises(InvalidFlowError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=f"{DATAS_DIR}/webClassification3.jsonl",
                column_mapping={"question": "${data.question}", "context": "${data.context}"},
                variant="${not_exist.variant_0}",
            )
        assert "Node not_exist not found in flow" in str(e.value)

        # invalid variant format
        with pytest.raises(UserErrorException) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=f"{DATAS_DIR}/webClassification3.jsonl",
                column_mapping={"question": "${data.question}", "context": "${data.context}"},
                variant="v",
            )
        assert "Invalid variant format: v, variant should be in format of ${TUNING_NODE.VARIANT}" in str(e.value)

    def test_basic_evaluation(self, azure_open_ai_connection: AzureOpenAIConnection, local_client, pf):
        result = pf.run(
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
        )
        assert local_client.runs.get(result.name).status == "Completed"

        eval_result = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            run=result.name,
            column_mapping={
                "prediction": "${run.outputs.output}",
                # evaluation reference run.inputs
                # NOTE: we need this value to guard behavior when a run reference another run's inputs
                "variant_id": "${run.inputs.key}",
                # can reference other columns in data which doesn't exist in base run's inputs
                "groundtruth": "${run.inputs.extra_key}",
            },
        )
        assert local_client.runs.get(eval_result.name).status == "Completed"

    def test_flow_demo(self, azure_open_ai_connection, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        column_mapping = {
            "groundtruth": "${data.answer}",
            "prediction": "${run.outputs.category}",
            "variant_id": "${data.variant_id}",
        }

        metrics = {}
        for flow_name, output_key in [
            ("web_classification", "baseline"),
            ("web_classification_v1", "v1"),
            ("web_classification_v2", "v2"),
        ]:
            v = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)

            metrics[output_key] = pf.run(
                flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
                data=data_path,
                run=v,
                column_mapping=column_mapping,
            )

    def test_submit_run_from_yaml(self, local_client, pf):
        run_id = str(uuid.uuid4())
        run = create_yaml_run(source=f"{RUNS_DIR}/sample_bulk_run.yaml", params_override=[{"name": run_id}])

        assert local_client.runs.get(run.name).status == "Completed"

        eval_run = create_yaml_run(
            source=f"{RUNS_DIR}/sample_eval_run.yaml",
            params_override=[{"run": run_id}],
        )
        assert local_client.runs.get(eval_run.name).status == "Completed"

    @pytest.mark.usefixtures("enable_logger_propagate")
    def test_submit_run_with_extra_params(self, pf, caplog):
        run_id = str(uuid.uuid4())
        run = create_yaml_run(source=f"{RUNS_DIR}/extra_field.yaml", params_override=[{"name": run_id}])
        assert pf.runs.get(run.name).status == "Completed"
        assert "Run schema validation warnings. Unknown fields found" in caplog.text

    def test_run_with_connection(self, local_client, local_aoai_connection, pf):
        # remove connection file to test connection resolving
        os.environ.pop(PROMPTFLOW_CONNECTIONS)
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
        )
        local_storage = LocalStorageOperations(result)
        detail = local_storage.load_detail()
        tuning_node = next((x for x in detail["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used default variant config
        assert tuning_node["inputs"]["temperature"] == 0.3

        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"

    def test_run_with_connection_overwrite(self, local_client, local_aoai_connection, local_alt_aoai_connection, pf):
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            connections={"classify_with_llm": {"connection": "new_ai_connection"}},
        )
        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"

    def test_custom_connection_overwrite(self, local_client, local_custom_connection, pf):
        result = pf.run(
            flow=f"{FLOWS_DIR}/custom_connection_flow",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            connections={"print_env": {"connection": "test_custom_connection"}},
        )
        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"

        # overwrite non-exist connection
        with pytest.raises(InvalidFlowError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/custom_connection_flow",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                connections={"print_env": {"new_connection": "test_custom_connection"}},
            )
        assert "Unsupported llm connection overwrite keys" in str(e.value)

    def test_basic_flow_with_package_tool_with_custom_strong_type_connection(
        self, install_custom_tool_pkg, local_client, pf
    ):
        result = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_package_tool_with_custom_strong_type_connection",
            data=f"{FLOWS_DIR}/flow_with_package_tool_with_custom_strong_type_connection/data.jsonl",
            connections={"My_First_Tool_00f8": {"connection": "custom_strong_type_connection"}},
        )
        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"

    def test_basic_flow_with_script_tool_with_custom_strong_type_connection(
        self, install_custom_tool_pkg, local_client, pf
    ):
        # Prepare custom connection
        from promptflow.connections import CustomConnection

        conn = CustomConnection(name="custom_connection_2", secrets={"api_key": "test"}, configs={"api_url": "test"})
        local_client.connections.create_or_update(conn)

        result = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_script_tool_with_custom_strong_type_connection",
            data=f"{FLOWS_DIR}/flow_with_script_tool_with_custom_strong_type_connection/data.jsonl",
        )
        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"

    def test_run_with_connection_overwrite_non_exist(self, local_client, local_aoai_connection, pf):
        # overwrite non_exist connection
        with pytest.raises(ConnectionNotFoundError):
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=f"{DATAS_DIR}/webClassification1.jsonl",
                connections={"classify_with_llm": {"connection": "Not_exist"}},
            )

    def test_run_reference_failed_run(self, pf):
        failed_run = pf.run(
            flow=f"{FLOWS_DIR}/failed_flow",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"text": "${data.url}"},
        )
        # "update" run status to failed since currently all run will be completed unless there's bug
        pf.runs.update(
            name=failed_run.name,
            status="Failed",
        )

        run_name = str(uuid.uuid4())
        with pytest.raises(UserErrorException) as e:
            pf.run(
                name=run_name,
                flow=f"{FLOWS_DIR}/custom_connection_flow",
                run=failed_run,
                connections={"print_env": {"connection": "test_custom_connection"}},
            )
        assert "is not completed, got status" in str(e.value)

        # run should not be created
        with pytest.raises(RunNotFoundError):
            pf.runs.get(name=run_name)

    def test_referenced_output_not_exist(self, pf: PFClient) -> None:
        # failed run won't generate output
        failed_run = pf.run(
            flow=f"{FLOWS_DIR}/failed_flow",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"text": "${data.url}"},
        )

        run_name = str(uuid.uuid4())
        run = pf.run(
            name=run_name,
            run=failed_run,
            flow=f"{FLOWS_DIR}/failed_flow",
            column_mapping={"text": "${run.outputs.text}"},
        )
        assert_run_with_invalid_column_mapping(pf, run)

    def test_connection_overwrite_file(self, local_client, local_aoai_connection):
        run = create_yaml_run(
            source=f"{RUNS_DIR}/run_with_connections.yaml",
        )
        run = local_client.runs.get(name=run.name)
        assert run.status == "Completed"

    def test_connection_overwrite_model(self, local_client, local_aoai_connection):
        run = create_yaml_run(
            source=f"{RUNS_DIR}/run_with_connections_model.yaml",
        )
        run = local_client.runs.get(name=run.name)
        assert run.status == "Completed"

    def test_resolve_connection(self, local_client, local_aoai_connection):
        flow = load_flow(f"{FLOWS_DIR}/web_classification_no_variants")
        connections = SubmitterHelper.resolve_connections(flow, local_client)
        assert local_aoai_connection.name in connections

    def test_run_with_env_overwrite(self, local_client, local_aoai_connection):
        run = create_yaml_run(
            source=f"{RUNS_DIR}/run_with_env.yaml",
        )
        outputs = local_client.runs._get_outputs(run=run)
        assert outputs["output"][0] == local_aoai_connection.api_base

    def test_pf_run_with_env_overwrite(self, local_client, local_aoai_connection, pf):
        run = pf.run(
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
        )
        outputs = local_client.runs._get_outputs(run=run)
        assert outputs["output"][0] == local_aoai_connection.api_base

    def test_eval_run_not_exist(self, pf):
        name = str(uuid.uuid4())
        with pytest.raises(RunNotFoundError) as e:
            pf.runs.create_or_update(
                run=Run(
                    name=name,
                    flow=Path(f"{FLOWS_DIR}/classification_accuracy_evaluation"),
                    run="not_exist",
                    column_mapping={
                        "groundtruth": "${data.answer}",
                        "prediction": "${run.outputs.category}",
                        # evaluation reference run.inputs
                        "url": "${run.inputs.url}",
                    },
                )
            )
        assert "Run name 'not_exist' cannot be found" in str(e.value)
        # run should not be created
        with pytest.raises(RunNotFoundError):
            pf.runs.get(name=name)

    def test_eval_run_data_deleted(self, pf):
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copy(f"{DATAS_DIR}/env_var_names.jsonl", temp_dir)

            result = pf.run(
                flow=f"{FLOWS_DIR}/print_env_var",
                data=f"{temp_dir}/env_var_names.jsonl",
            )
            assert pf.runs.get(result.name).status == "Completed"

            # delete original run's input data
            os.remove(f"{temp_dir}/env_var_names.jsonl")

            with pytest.raises(UserErrorException) as e:
                pf.run(
                    flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
                    run=result.name,
                    column_mapping={
                        "prediction": "${run.outputs.output}",
                        # evaluation reference run.inputs
                        # NOTE: we need this value to guard behavior when a run reference another run's inputs
                        "variant_id": "${run.inputs.key}",
                        # can reference other columns in data which doesn't exist in base run's inputs
                        "groundtruth": "${run.inputs.extra_key}",
                    },
                )
            assert "Please make sure it exists and not deleted." in str(e.value)

    def test_eval_run_data_not_exist(self, pf):
        base_run = pf.run(
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
        )
        assert pf.runs.get(base_run.name).status == "Completed"

        eval_run = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            run=base_run.name,
            column_mapping={
                "prediction": "${run.outputs.output}",
                # evaluation reference run.inputs
                # NOTE: we need this value to guard behavior when a run reference another run's inputs
                "variant_id": "${run.inputs.key}",
                # can reference other columns in data which doesn't exist in base run's inputs
                "groundtruth": "${run.inputs.extra_key}",
            },
        )

        result = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            run=eval_run.name,
            column_mapping={
                "prediction": "${run.outputs.output}",
                # evaluation reference run.inputs
                # NOTE: we need this value to guard behavior when a run reference another run's inputs
                "variant_id": "${run.inputs.key}",
                # can reference other columns in data which doesn't exist in base run's inputs
                "groundtruth": "${run.inputs.extra_key}",
            },
        )
        # Run failed because run inputs data is None, and error will be in the run output error.json
        assert result.status == "Failed"

    def test_create_run_with_tags(self, pf):
        name = str(uuid.uuid4())
        display_name = "test_run_with_tags"
        tags = {"key1": "tag1"}
        run = pf.run(
            name=name,
            display_name=display_name,
            tags=tags,
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
        )
        assert run.name == name
        assert "test_run_with_tags" == run.display_name
        assert run.tags == tags

    def test_run_display_name(self, pf):
        # use run name if not specify display_name
        run = pf.runs.create_or_update(
            run=Run(
                flow=Path(f"{FLOWS_DIR}/print_env_var"),
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
            )
        )
        assert run.display_name == run.name
        assert "print_env_var" in run.display_name

        # will respect if specified in run
        base_run = pf.runs.create_or_update(
            run=Run(
                flow=Path(f"{FLOWS_DIR}/print_env_var"),
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
                display_name="my_run",
            )
        )
        assert base_run.display_name == "my_run"

        run = pf.runs.create_or_update(
            run=Run(
                flow=Path(f"{FLOWS_DIR}/print_env_var"),
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
                display_name="my_run_${variant_id}_${run}",
                run=base_run,
            )
        )
        assert run.display_name == f"my_run_variant_0_{base_run.name}"

        run = pf.runs.create_or_update(
            run=Run(
                flow=Path(f"{FLOWS_DIR}/print_env_var"),
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
                display_name="my_run_${timestamp}",
                run=base_run,
            )
        )
        assert "${timestamp}" not in run.display_name

    def test_run_dump(self, azure_open_ai_connection: AzureOpenAIConnection, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        # in fact, `pf.run` will internally query the run from db in `RunSubmitter`
        # explicitly call ORM get here to emphasize the dump operatoin
        # if no dump operation, a RunNotFoundError will be raised here
        pf.runs.get(run.name)

    def test_run_list(self, azure_open_ai_connection: AzureOpenAIConnection, pf) -> None:
        # create a run to ensure there is at least one run in the db
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        # not specify `max_result` here, so that if there are legacy runs in the db
        # list runs API can collect them, and can somehow cover legacy schema
        runs = pf.runs.list()
        assert len(runs) >= 1

    def test_stream_run_summary(self, azure_open_ai_connection: AzureOpenAIConnection, local_client, capfd, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        local_client.runs.stream(run.name)
        out, _ = capfd.readouterr()
        print(out)
        assert 'Run status: "Completed"' in out
        assert "Output path: " in out

    def test_stream_incomplete_run_summary(
        self, azure_open_ai_connection: AzureOpenAIConnection, local_client, capfd, pf
    ) -> None:
        # use wrong data to create a failed run
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        name = str(uuid.uuid4())
        run = pf.run(
            flow=f"{FLOWS_DIR}/failed_flow",
            data=data_path,
            column_mapping={"text": "${data.url}"},
            name=name,
        )
        local_client.runs.stream(run.name)
        # assert error message in stream API
        out, _ = capfd.readouterr()
        assert 'Run status: "Completed"' in out
        # won't print exception, use can get it from run._to_dict()
        # assert "failed with exception" in out

    def test_run_data_not_provided(self, pf):
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
            )
        assert "at least one of data or run must be provided" in str(e)

    def test_get_details(self, azure_open_ai_connection: AzureOpenAIConnection, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
        )

        from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations

        local_storage = LocalStorageOperations(run)
        # there should be line_number in original DataFrame, but not in details DataFrame
        # as we will set index on line_number to ensure the order
        outputs = pd.read_json(local_storage._outputs_path, orient="records", lines=True)
        details = pf.get_details(run)
        assert "line_number" in outputs and "line_number" not in details

    def test_visualize_run(self, azure_open_ai_connection: AzureOpenAIConnection, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run1 = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
        )
        run2 = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=run1.name,
            column_mapping={
                "groundtruth": "${data.answer}",
                "prediction": "${run.outputs.category}",
                "variant_id": "${data.variant_id}",
            },
        )
        pf.visualize([run1, run2])

    def test_incomplete_run_visualize(
        self, azure_open_ai_connection: AzureOpenAIConnection, pf, capfd: pytest.CaptureFixture
    ) -> None:
        failed_run = pf.run(
            flow=f"{FLOWS_DIR}/failed_flow",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"text": "${data.url}"},
        )
        # "update" run status to failed since currently all run will be completed unless there's bug
        pf.runs.update(
            name=failed_run.name,
            status="Failed",
        )

        # patch logger.error to print, so that we can capture the error message using capfd
        from promptflow._sdk.operations import _run_operations

        _run_operations.logger.error = print

        pf.visualize(failed_run)
        captured = capfd.readouterr()
        expected_error_message = (
            f"Cannot visualize non-completed run. Run {failed_run.name!r} is not completed, the status is 'Failed'."
        )
        assert expected_error_message in captured.out

    def test_flow_bulk_run_with_additional_includes(self, azure_open_ai_connection: AzureOpenAIConnection, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification_with_additional_include", data=data_path)

        additional_includes = _get_additional_includes(run.flow / "flow.dag.yaml")
        snapshot_path = Path.home() / ".promptflow" / ".runs" / run.name / "snapshot"
        for item in additional_includes:
            assert (snapshot_path / Path(item).name).exists()
        # Addition includes in snapshot is removed
        additional_includes = _get_additional_includes(snapshot_path / "flow.dag.yaml")
        assert not additional_includes

    def test_input_mapping_source_not_found_error(self, azure_open_ai_connection: AzureOpenAIConnection, pf):
        # input_mapping source not found error won't create run
        name = str(uuid.uuid4())
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"not_exist": "${data.not_exist_key}"},
            name=name,
        )
        assert_run_with_invalid_column_mapping(pf, run)

    def test_input_mapping_with_dict(self, azure_open_ai_connection: AzureOpenAIConnection, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        run = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_dict_input",
            data=data_path,
            column_mapping={"key": {"value": "1"}, "url": "${data.url}"},
        )
        outputs = pf.runs._get_outputs(run=run)
        assert "dict" in outputs["output"][0]

    def test_run_exist_error(self, pf):
        name = str(uuid.uuid4())
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        pf.run(
            name=name,
            flow=f"{FLOWS_DIR}/flow_with_dict_input",
            data=data_path,
            column_mapping={"key": {"value": "1"}, "url": "${data.url}"},
        )

        # create a new run won't affect original run
        with pytest.raises(RunExistsError):
            pf.run(
                name=name,
                flow=f"{FLOWS_DIR}/flow_with_dict_input",
                data=data_path,
                column_mapping={"key": {"value": "1"}, "url": "${data.url}"},
            )
        run = pf.runs.get(name)
        assert run.status == RunStatus.COMPLETED
        assert not os.path.exists(run._output_path / LocalStorageFilenames.EXCEPTION)

    def test_run_local_storage_structure(self, local_client, pf) -> None:
        run = create_run_against_multi_line_data(pf)
        local_storage = LocalStorageOperations(local_client.runs.get(run.name))
        run_output_path = local_storage.path
        assert (Path(run_output_path) / "flow_outputs").is_dir()
        assert (Path(run_output_path) / "flow_outputs" / "output.jsonl").is_file()
        assert (Path(run_output_path) / "flow_artifacts").is_dir()
        # 3 line runs for webClassification3.jsonl
        assert len([_ for _ in (Path(run_output_path) / "flow_artifacts").iterdir()]) == 3
        assert (Path(run_output_path) / "node_artifacts").is_dir()
        # 5 nodes web classification flow DAG
        assert len([_ for _ in (Path(run_output_path) / "node_artifacts").iterdir()]) == 5

    def test_run_snapshot_with_flow_tools_json(self, local_client, pf) -> None:
        run = create_run_against_multi_line_data(pf)
        local_storage = LocalStorageOperations(local_client.runs.get(run.name))
        assert (local_storage._snapshot_folder_path / ".promptflow").is_dir()
        assert (local_storage._snapshot_folder_path / ".promptflow" / "flow.tools.json").is_file()

    def test_get_metrics_format(self, local_client, pf) -> None:
        run1 = create_run_against_multi_line_data(pf)
        run2 = create_run_against_run(pf, run1)
        # ensure the result is a flatten dict
        assert local_client.runs.get_metrics(run2.name).keys() == {"accuracy"}

    def test_get_detail_format(self, local_client, pf) -> None:
        run = create_run_against_multi_line_data(pf)
        # data is a jsonl file, so we can know the number of line runs
        with open(f"{DATAS_DIR}/webClassification3.jsonl", "r") as f:
            data = f.readlines()
        number_of_lines = len(data)

        local_storage = LocalStorageOperations(local_client.runs.get(run.name))
        detail = local_storage.load_detail()

        assert isinstance(detail, dict)
        # flow runs
        assert "flow_runs" in detail
        assert isinstance(detail["flow_runs"], list)
        assert len(detail["flow_runs"]) == number_of_lines
        # node runs
        assert "node_runs" in detail
        assert isinstance(detail["node_runs"], list)

    def test_run_logs(self, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        run = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_user_output",
            data=data_path,
            column_mapping={"key": {"value": "1"}, "url": "${data.url}"},
        )
        local_storage = LocalStorageOperations(run=run)
        logs = local_storage.logger.get_logs()
        # For Batch run, the executor uses bulk logger to print logs, and only prints the error log of the nodes.
        existing_keywords = ["execution", "execution.bulk", "WARNING", "error log"]
        assert all([keyword in logs for keyword in existing_keywords])
        non_existing_keywords = ["execution.flow", "user log"]
        assert all([keyword not in logs for keyword in non_existing_keywords])

    def test_get_detail_against_partial_fail_run(self, pf) -> None:
        run = pf.run(
            flow=f"{FLOWS_DIR}/partial_fail",
            data=f"{FLOWS_DIR}/partial_fail/data.jsonl",
        )
        detail = pf.runs.get_details(name=run.name)
        detail.fillna("", inplace=True)
        assert len(detail) == 3

    def test_flow_with_only_static_values(self, pf):
        name = str(uuid.uuid4())
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        with pytest.raises(UserErrorException) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/flow_with_dict_input",
                data=data_path,
                column_mapping={"key": {"value": "1"}},
                name=name,
            )

        assert "Column mapping must contain at least one mapping binding" in str(e.value)
        # run should not be created
        with pytest.raises(RunNotFoundError):
            pf.runs.get(name=name)

    def test_error_message_dump(self, pf):
        failed_run = pf.run(
            flow=f"{FLOWS_DIR}/failed_flow",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"text": "${data.url}"},
        )
        # even if all lines failed, the bulk run's status is completed.
        assert failed_run.status == "Completed"
        # error messages will store in local
        local_storage = LocalStorageOperations(failed_run)

        assert os.path.exists(local_storage._exception_path)
        exception = local_storage.load_exception()
        assert "Failed to run 1/1 lines. First error message is" in exception["message"]
        # line run failures will be stored in additionalInfo
        assert len(exception["additionalInfo"][0]["info"]["errors"]) == 1

        # show run will get error message
        run = pf.runs.get(name=failed_run.name)
        run_dict = run._to_dict()
        assert "error" in run_dict
        assert run_dict["error"] == exception

    def test_system_metrics_in_properties(self, pf) -> None:
        run = create_run_against_multi_line_data(pf)
        assert FlowRunProperties.SYSTEM_METRICS in run.properties
        assert isinstance(run.properties[FlowRunProperties.SYSTEM_METRICS], dict)
        assert "total_tokens" in run.properties[FlowRunProperties.SYSTEM_METRICS]

    def test_run_get_inputs(self, pf):
        # inputs should be persisted when defaults are used
        run = pf.run(
            flow=f"{FLOWS_DIR}/default_input",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
        )
        inputs = pf.runs._get_inputs(run=run)
        assert inputs == {
            "line_number": [0],
            "input_bool": [False],
            "input_dict": [{}],
            "input_list": [[]],
            "input_str": ["input value from default"],
        }

        # inputs should be persisted when data value are used
        run = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_dict_input",
            data=f"{DATAS_DIR}/dictInput1.jsonl",
        )
        inputs = pf.runs._get_inputs(run=run)
        assert inputs == {"key": [{"key": "value in data"}], "line_number": [0]}

        # inputs should be persisted when column-mapping are used
        run = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_dict_input",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"key": {"value": "value in column-mapping"}, "url": "${data.url}"},
        )
        inputs = pf.runs._get_inputs(run=run)
        assert inputs == {
            "key": [{"value": "value in column-mapping"}],
            "line_number": [0],
            "url": ["https://www.youtube.com/watch?v=o5ZQyXaAv1g"],
        }

    def test_executor_logs_in_batch_run_logs(self, pf) -> None:
        run = create_run_against_multi_line_data_without_llm(pf)
        local_storage = LocalStorageOperations(run=run)
        logs = local_storage.logger.get_logs()
        # below warning is printed by executor before the batch run executed
        # the warning message results from we do not use column mapping
        # so it is expected to be printed here
        assert "Starting run without column mapping may lead to unexpected results." in logs

    def test_basic_image_flow_bulk_run(self, pf, local_client) -> None:
        image_flow_path = f"{FLOWS_DIR}/python_tool_with_simple_image"
        data_path = f"{image_flow_path}/image_inputs/inputs.jsonl"

        result = pf.run(flow=image_flow_path, data=data_path, column_mapping={"image": "${data.image}"})
        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

    def test_openai_vision_image_flow_bulk_run(self, pf, local_client) -> None:
        image_flow_path = f"{FLOWS_DIR}/python_tool_with_openai_vision_image"
        data_path = f"{image_flow_path}/inputs.jsonl"

        result = pf.run(flow=image_flow_path, data=data_path, column_mapping={"image": "${data.image}"})
        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

    def test_python_tool_with_composite_image(self, pf) -> None:
        image_flow_path = f"{FLOWS_DIR}/python_tool_with_composite_image"
        data_path = f"{image_flow_path}/inputs.jsonl"

        result = pf.run(
            flow=image_flow_path,
            data=data_path,
            column_mapping={
                "image_list": "${data.image_list}",
                "image_dict": "${data.image_dict}",
            },
        )
        run = pf.runs.get(name=result.name)
        assert run.status == "Completed"
        # no error when processing lines
        assert "error" not in run._to_dict()

        # test input from output
        result = pf.run(
            run=result,
            flow=image_flow_path,
            column_mapping={
                "image_list": "${run.outputs.output}"
                # image dict will use default value, which is relative to flow's folder
            },
        )
        run = pf.runs.get(name=result.name)
        assert run.status == "Completed"
        # no error when processing lines
        assert "error" not in run._to_dict()

    def test_image_without_default(self, pf):
        image_flow_path = f"{FLOWS_DIR}/python_tool_with_simple_image_without_default"
        data_path = f"{DATAS_DIR}/image_inputs"

        result = pf.run(
            flow=image_flow_path,
            data=data_path,
            column_mapping={
                "image_1": "${data.image}",
                "image_2": "${data.image}",
            },
        )
        run = pf.runs.get(name=result.name)
        assert run.status == "Completed", run.name
        # no error when processing lines
        assert "error" not in run._to_dict(), run.name

    def test_get_details_for_image_in_flow(self, pf) -> None:
        image_flow_path = f"{FLOWS_DIR}/python_tool_with_simple_image"
        data_path = f"{image_flow_path}/image_inputs/inputs.jsonl"
        run = pf.run(
            flow=image_flow_path,
            data=data_path,
            column_mapping={"image": "${data.image}"},
        )
        details = pf.get_details(run.name)
        for i in range(len(details)):
            input_image_path = details["inputs.image"][i]["data:image/png;path"]
            assert Path(input_image_path).is_absolute()
            output_image_path = details["outputs.output"][i]["data:image/png;path"]
            assert Path(output_image_path).is_absolute()

    def test_stream_raise_on_error_false(self, pf: PFClient, capfd: pytest.CaptureFixture) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"not_exist": "${data.not_exist_key}"},
            name=str(uuid.uuid4()),
        )
        # raise_on_error=False, will print error message in stdout
        pf.stream(run.name, raise_on_error=False)
        out, _ = capfd.readouterr()
        assert "The input for batch run is incorrect. Couldn't find these mapping relations" in out

    def test_stream_canceled_run(self, pf: PFClient, capfd: pytest.CaptureFixture) -> None:
        run = create_run_against_multi_line_data_without_llm(pf)
        pf.runs.update(name=run.name, status=RunStatus.CANCELED)
        # (default) raise_on_error=True
        with pytest.raises(InvalidRunStatusError):
            pf.stream(run.name)
        # raise_on_error=False
        pf.stream(run.name, raise_on_error=False)
        out, _ = capfd.readouterr()
        assert "Run is canceled." in out

    def test_specify_run_output_path(self, pf: PFClient, mocker: MockerFixture) -> None:
        # mock to imitate user specify config run.output_path
        specified_run_output_path = (Path.home() / PROMPT_FLOW_DIR_NAME / ".mock").resolve().as_posix()
        with mocker.patch(
            "promptflow._sdk._configuration.Configuration.get_run_output_path",
            return_value=specified_run_output_path,
        ):
            run = create_run_against_multi_line_data_without_llm(pf)
            local_storage = LocalStorageOperations(run=run)
            expected_output_path_prefix = (Path(specified_run_output_path) / run.name).resolve().as_posix()
            assert local_storage.outputs_folder.as_posix().startswith(expected_output_path_prefix)

    def test_override_run_output_path_in_pf_client(self) -> None:
        specified_run_output_path = (Path.home() / PROMPT_FLOW_DIR_NAME / ".another_mock").resolve().as_posix()
        pf = PFClient(config={"run.output_path": specified_run_output_path})
        run = create_run_against_multi_line_data_without_llm(pf)
        local_storage = LocalStorageOperations(run=run)
        expected_output_path_prefix = (Path(specified_run_output_path) / run.name).resolve().as_posix()
        assert local_storage.outputs_folder.as_posix().startswith(expected_output_path_prefix)

    def test_specify_run_output_path_with_macro(self, pf: PFClient, mocker: MockerFixture) -> None:
        # mock to imitate user specify invalid config run.output_path
        with mocker.patch(
            "promptflow._sdk._configuration.Configuration.get_run_output_path",
            return_value=f"{FLOW_DIRECTORY_MACRO_IN_CONFIG}/.promptflow",
        ):
            for _ in range(3):
                run = create_run_against_multi_line_data_without_llm(pf)
                local_storage = LocalStorageOperations(run=run)
                expected_path_prefix = Path(FLOWS_DIR) / "print_env_var" / ".promptflow" / run.name
                expected_path_prefix = expected_path_prefix.resolve().as_posix()
                assert local_storage.outputs_folder.as_posix().startswith(expected_path_prefix)

    def test_specify_run_output_path_with_invalid_macro(self, pf: PFClient, mocker: MockerFixture) -> None:
        # mock to imitate user specify invalid config run.output_path
        with mocker.patch(
            "promptflow._sdk._configuration.Configuration.get_run_output_path",
            # this case will happen when user manually modifies ~/.promptflow/pf.yaml
            return_value=f"{FLOW_DIRECTORY_MACRO_IN_CONFIG}",
        ):
            run = create_run_against_multi_line_data_without_llm(pf)
            # as the specified run output path is invalid
            # the actual run output path will be the default value
            local_storage = LocalStorageOperations(run=run)
            expected_output_path_prefix = (Path.home() / PROMPT_FLOW_DIR_NAME / ".runs" / run.name).resolve().as_posix()
            assert local_storage.outputs_folder.as_posix().startswith(expected_output_path_prefix)

    def test_failed_run_to_dict_exclude(self, pf):
        failed_run = pf.run(
            flow=f"{FLOWS_DIR}/failed_flow",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"text": "${data.url}"},
        )
        default = failed_run._to_dict()
        # CLI will exclude additional info and debug info
        exclude = failed_run._to_dict(exclude_additional_info=True, exclude_debug_info=True)
        assert "additionalInfo" in default["error"] and "additionalInfo" not in exclude["error"]
        assert "debugInfo" in default["error"] and "debugInfo" not in exclude["error"]

    def test_create_run_with_existing_run_folder(self, pf):
        # TODO: Should use fixture to create an run and download it to be used here.
        run_name = "web_classification_variant_0_20231205_120253_104100"

        # clean the run if exists
        from promptflow._cli._utils import _try_delete_existing_run_record

        _try_delete_existing_run_record(run_name)

        # assert the run doesn't exist
        with pytest.raises(RunNotFoundError):
            pf.runs.get(run_name)

        # create the run with run folder
        run_folder = f"{RUNS_DIR}/{run_name}"
        run = Run._load_from_source(source=run_folder)
        pf.runs.create_or_update(run)

        # test with other local run operations
        run = pf.runs.get(run_name)
        assert run.name == run_name
        details = pf.get_details(run_name)
        assert details.shape == (3, 5)
        metrics = pf.runs.get_metrics(run_name)
        assert metrics == {}
        pf.stream(run_name)
        pf.visualize([run_name])

    def test_aggregation_node_failed(self, pf):
        failed_run = pf.run(
            flow=f"{FLOWS_DIR}/aggregation_node_failed",
            data=f"{FLOWS_DIR}/aggregation_node_failed/data.jsonl",
        )
        # even if all lines failed, the bulk run's status is completed.
        assert failed_run.status == "Completed"
        # error messages will store in local
        local_storage = LocalStorageOperations(failed_run)

        assert os.path.exists(local_storage._exception_path)
        exception = local_storage.load_exception()
        assert "First error message is" in exception["message"]
        # line run failures will be stored in additionalInfo
        assert len(exception["additionalInfo"][0]["info"]["errors"]) == 1

        # show run will get error message
        run = pf.runs.get(name=failed_run.name)
        run_dict = run._to_dict()
        assert "error" in run_dict
        assert run_dict["error"] == exception

    def test_get_details_against_partial_completed_run(self, pf: PFClient, monkeypatch) -> None:
        # TODO: remove this patch after executor switch to default spawn
        monkeypatch.setenv("PF_BATCH_METHOD", "spawn")

        flow_mod2 = f"{FLOWS_DIR}/mod-n/two"
        flow_mod3 = f"{FLOWS_DIR}/mod-n/three"
        data_path = f"{DATAS_DIR}/numbers.jsonl"
        # batch run against data
        run1 = pf.run(
            flow=flow_mod2,
            data=data_path,
            column_mapping={"number": "${data.value}"},
        )
        pf.runs.stream(run1)
        details1 = pf.get_details(run1)
        assert len(details1) == 20
        assert len(details1.loc[details1["outputs.output"] != "(Failed)"]) == 10
        # assert to ensure inputs and outputs are aligned
        for _, row in details1.iterrows():
            if str(row["outputs.output"]) != "(Failed)":
                assert int(row["inputs.number"]) == int(row["outputs.output"])

        # batch run against previous run
        run2 = pf.run(
            flow=flow_mod3,
            run=run1,
            column_mapping={"number": "${run.outputs.output}"},
        )
        pf.runs.stream(run2)
        details2 = pf.get_details(run2)
        assert len(details2) == 10
        assert len(details2.loc[details2["outputs.output"] != "(Failed)"]) == 4
        # assert to ensure inputs and outputs are aligned
        for _, row in details2.iterrows():
            if str(row["outputs.output"]) != "(Failed)":
                assert int(row["inputs.number"]) == int(row["outputs.output"])

        monkeypatch.delenv("PF_BATCH_METHOD")

    def test_flow_with_nan_inf(self, pf: PFClient, monkeypatch) -> None:
        # TODO: remove this patch after executor switch to default spawn
        monkeypatch.setenv("PF_BATCH_METHOD", "spawn")

        run = pf.run(
            flow=f"{FLOWS_DIR}/flow-with-nan-inf",
            data=f"{DATAS_DIR}/numbers.jsonl",
            column_mapping={"number": "${data.value}"},
        )
        pf.stream(run)
        local_storage = LocalStorageOperations(run=run)

        # default behavior: no special logic for nan and inf
        detail = local_storage.load_detail()
        first_line_run_output = detail["flow_runs"][0]["output"]["output"]
        assert isinstance(first_line_run_output["nan"], float)
        assert np.isnan(first_line_run_output["nan"])
        assert isinstance(first_line_run_output["inf"], float)
        assert np.isinf(first_line_run_output["inf"])

        # handles nan and inf, which is real scenario during visualize
        detail = local_storage.load_detail(parse_const_as_str=True)
        first_line_run_output = detail["flow_runs"][0]["output"]["output"]
        assert isinstance(first_line_run_output["nan"], str)
        assert first_line_run_output["nan"] == "NaN"
        assert isinstance(first_line_run_output["inf"], str)
        assert first_line_run_output["inf"] == "Infinity"

        monkeypatch.delenv("PF_BATCH_METHOD")

    def test_flow_with_nan_inf_metrics(self, pf: PFClient, monkeypatch) -> None:
        # TODO: remove this patch after executor switch to default spawn
        monkeypatch.setenv("PF_BATCH_METHOD", "spawn")

        run = pf.run(
            flow=f"{FLOWS_DIR}/flow-with-nan-inf-metrics",
            data=f"{DATAS_DIR}/numbers.jsonl",
            column_mapping={"number": "${data.value}"},
        )
        pf.stream(run)
        local_storage = LocalStorageOperations(run=run)
        # default behavior: no special logic for nan and inf
        metrics = local_storage.load_metrics()
        assert isinstance(metrics["nan_metrics"], float) and np.isnan(metrics["nan_metrics"])
        assert isinstance(metrics["inf_metrics"], float) and np.isinf(metrics["inf_metrics"])

        # handles nan and inf, which is real scenario during visualize
        metrics = local_storage.load_metrics(parse_const_as_str=True)
        assert isinstance(metrics["nan_metrics"], str) and metrics["nan_metrics"] == "NaN"
        assert isinstance(metrics["inf_metrics"], str) and metrics["inf_metrics"] == "Infinity"

        monkeypatch.delenv("PF_BATCH_METHOD")

    @pytest.mark.parametrize(
        "run_params, expected_snapshot_yaml, extra_check, expected_details",
        [
            pytest.param(
                {
                    "flow": "entry:my_flow",
                    "code": f"{EAGER_FLOWS_DIR}/simple_without_yaml",
                    "data": f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                },
                {
                    "entry": "entry:my_flow",
                    "inputs": {"input_val": {"type": "string"}},
                    "outputs": {"output": {"type": "string"}},
                },
                # the YAML file will not exist in user's folder
                lambda: not Path(f"{EAGER_FLOWS_DIR}/simple_without_yaml/flow.flex.yaml").exists(),
                {"inputs.input_val": ["input1"], "inputs.line_number": [0], "outputs.output": ["(Failed)"]},
                id="without_yaml",
            ),
            pytest.param(
                {
                    "flow": Path(f"{EAGER_FLOWS_DIR}/simple_with_yaml"),
                    "data": f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                },
                {
                    "entry": "entry:my_flow",
                    "inputs": {"input_val": {"type": "string", "default": "gpt"}},
                    "outputs": {"output": {"type": "string"}},
                },
                # signature not in original YAML
                lambda: "inputs" not in load_yaml(f"{EAGER_FLOWS_DIR}/simple_with_yaml/flow.flex.yaml"),
                {"inputs.input_val": ["input1"], "inputs.line_number": [0], "outputs.output": ["Hello world! input1"]},
                id="with_yaml",
            ),
            pytest.param(
                {
                    "flow": "entry2:my_flow2",
                    "code": f"{EAGER_FLOWS_DIR}/multiple_entries",
                    "data": f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                },
                {
                    "entry": "entry2:my_flow2",
                    "outputs": {"output": {"type": "string"}},
                },
                # entry is not changed in original YAML
                lambda: load_yaml(f"{EAGER_FLOWS_DIR}/multiple_entries/flow.flex.yaml")["entry"] == "entry1:my_flow1",
                {"inputs.line_number": [0], "outputs.output": ["entry2flow2"]},
                id="entry_override",
            ),
            pytest.param(
                {
                    "flow": my_entry,
                    "data": f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                    # set code folder to avoid snapshot too big
                    "code": f"{EAGER_FLOWS_DIR}/multiple_entries",
                    "column_mapping": {"input1": "${data.input_val}"},
                },
                {
                    "entry": "sdk_cli_test.e2etests.test_flow_run:my_entry",
                    "inputs": {"input1": {"type": "string"}},
                    "outputs": {"output": {"type": "string"}},
                },
                lambda: True,
                {"inputs.input1": ["input1"], "inputs.line_number": [0], "outputs.output": ["input1"]},
                id="with_func",
            ),
            pytest.param(
                {
                    "flow": my_async_entry,
                    "data": f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                    # set code folder to avoid snapshot too big
                    "code": f"{EAGER_FLOWS_DIR}/multiple_entries",
                    "column_mapping": {"input2": "${data.input_val}"},
                },
                {
                    "entry": "sdk_cli_test.e2etests.test_flow_run:my_async_entry",
                    "inputs": {"input2": {"type": "string"}},
                    "outputs": {"output": {"type": "string"}},
                },
                lambda: True,
                {"inputs.input2": ["input1"], "inputs.line_number": [0], "outputs.output": ["input1"]},
                id="with_async_func",
            ),
            pytest.param(
                {
                    "flow": Path(f"{EAGER_FLOWS_DIR}/code_yaml_signature_merge"),
                    "data": f"{EAGER_FLOWS_DIR}/code_yaml_signature_merge/data.jsonl",
                    "code": f"{EAGER_FLOWS_DIR}/code_yaml_signature_merge",
                    "column_mapping": {
                        "func_input1": "${data.func_input1}",
                        "func_input3": "${data.func_input3}",
                        "func_input2": "${data.func_input2}",
                    },
                    "init": {"obj_input1": "obj_input1", "obj_input2": 1, "obj_input3": "obj_input3"},
                },
                {
                    "entry": "partial_signatures:MyFlow",
                    "inputs": {
                        "func_input1": {"type": "string"},
                        "func_input2": {"type": "bool"},
                        "func_input3": {"type": "string"},
                    },
                    "init": {
                        "obj_input1": {"type": "string"},
                        "obj_input2": {"type": "int"},
                        "obj_input3": {"type": "string"},
                    },
                    "outputs": {"output": {"type": "string"}},
                },
                lambda: True,
                {
                    "inputs.func_input1": ["func_input"],
                    "inputs.func_input2": [False],
                    "inputs.func_input3": [3],
                    "inputs.line_number": [0],
                    "outputs.output": ["func_input"],
                },
                id="with_signature_merge",
            ),
        ],
    )
    def test_flex_flow_run(
        self,
        pf,
        run_params: dict,
        expected_snapshot_yaml: dict,
        extra_check: Callable[[], bool],
        expected_details: dict,
    ) -> None:
        run = pf.run(**run_params)
        # flex flow does not have variant
        assert "_variant_" not in run.name
        assert "_variant_" not in run.display_name
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

        assert extra_check()

        # will create a YAML in run snapshot
        local_storage = LocalStorageOperations(run=run)
        assert local_storage._dag_path.exists()

        yaml_dict = load_yaml(local_storage._dag_path)
        assert yaml_dict == expected_snapshot_yaml

        assert not local_storage._dag_path.read_text().startswith("!!omap")

        # actual result will be entry2:my_flow2
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == expected_details

    def test_flex_flow_with_local_imported_func(self, pf):
        # run eager flow against a function from local file
        with inject_sys_path(f"{EAGER_FLOWS_DIR}/multiple_entries"):
            from entry2 import my_flow2

            run = pf.run(
                flow=my_flow2,
                data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                # set code folder to avoid snapshot too big
                code=f"{EAGER_FLOWS_DIR}/multiple_entries",
                column_mapping={"input1": "${data.input_val}"},
            )
            assert run.status == "Completed"
            assert "error" not in run._to_dict()

            # actual result will be entry2:my_flow2
            details = pf.get_details(run.name)
            # convert DataFrame to dict
            details_dict = details.to_dict(orient="list")
            assert details_dict == {
                "inputs.input1": ["input1"],
                "inputs.line_number": [0],
                "outputs.output": ["entry2flow2"],
            }

    def test_flex_flow_with_imported_func(self, pf):
        # run eager flow against a function from module
        run = pf.run(
            flow=_parse_otel_span_status_code,
            data=f"{DATAS_DIR}/simple_eager_flow_data_numbers.jsonl",
            # set code folder to avoid snapshot too big
            code=f"{EAGER_FLOWS_DIR}/multiple_entries",
            column_mapping={"value": "${data.value}"},
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

        # actual result will be entry2:my_flow2
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.line_number": [0], "inputs.value": [0], "outputs.output": ["Unset"]}

    def test_eager_flow_run_in_working_dir(self, pf):
        working_dir = f"{EAGER_FLOWS_DIR}/multiple_entries"
        with _change_working_dir(working_dir):
            run = pf.run(
                flow="entry2:my_flow1",
                data="../../datas/simple_eager_flow_data.jsonl",
            )
            assert run.status == "Completed"
            assert "error" not in run._to_dict()

        # will create a YAML in run snapshot
        local_storage = LocalStorageOperations(run=run)
        assert local_storage._dag_path.exists()
        # original YAMl content not changed
        original_dict = load_yaml(f"{EAGER_FLOWS_DIR}/multiple_entries/flow.flex.yaml")
        assert original_dict["entry"] == "entry1:my_flow1"

        # actual result will be entry2:my_flow2
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.line_number": [0], "outputs.output": ["entry2flow1"]}

    def test_eager_flow_run_batch_resume(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/simple_with_random_fail")
        original_name = str(uuid.uuid4())
        original_run = pf.run(
            flow=flow_path,
            data=f"{EAGER_FLOWS_DIR}/simple_with_random_fail/inputs.jsonl",
            name=original_name,
        )
        assert original_run.status == "Completed"
        output_path = os.path.join(original_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            original_output = [json.loads(line) for line in file]
        original_success_count = len(original_output)

        resume_name = str(uuid.uuid4())
        resume_run = pf.run(
            resume_from=original_run,
            name=resume_name,
        )
        assert resume_run.name == resume_name
        assert resume_run._resume_from == original_name
        # assert new run resume from the original run
        output_path = os.path.join(resume_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            resume_output = [json.loads(line) for line in file]
        assert len(original_output) < len(resume_output)

        log_path = os.path.join(resume_run.properties["output_path"], "logs.txt")
        with open(log_path, "r") as file:
            log_text = file.read()
        assert f"Skipped the execution of {original_success_count} existing results." in log_text

    def test_eager_flow_test_invalid_cases(self, pf):
        # incorrect entry provided
        flow_path = Path(f"{EAGER_FLOWS_DIR}/incorrect_entry/")
        with pytest.raises(ValidationError) as e:
            pf.run(
                flow=flow_path,
                data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            )
        assert "Entry function my_func is not valid" in str(e.value)

    def test_eager_flow_run_with_additional_includes(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/flow_with_additional_includes")
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

    def test_get_incomplete_run(self, local_client, pf) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree(f"{FLOWS_DIR}/print_env_var", f"{temp_dir}/print_env_var")

            run = pf.run(
                flow=f"{temp_dir}/print_env_var",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
            )

            # remove flow dag
            os.unlink(f"{temp_dir}/print_env_var/flow.dag.yaml")

            # can still get run operations
            LocalStorageOperations(run=run)

            # can to_dict
            run._to_dict()

    def test_eager_flow_run_with_environment_variables(self, pf):
        # run's environment variables will override flow's environment variables
        flow_path = Path(f"{EAGER_FLOWS_DIR}/environment_variables")
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            environment_variables={"TEST": "RUN"},
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.line_number": [0], "outputs.output": ["Hello world! RUN"]}

        flow_path = Path(f"{EAGER_FLOWS_DIR}/environment_variables")
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.line_number": [0], "outputs.output": ["Hello world! VAL"]}

    def test_eager_flow_run_with_evc(self, pf):
        # run's evc can work
        flow_path = Path(f"{EAGER_FLOWS_DIR}/environment_variables")
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            environment_variables={"TEST": "${azure_open_ai_connection.api_type}"},
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.line_number": [0], "outputs.output": ["Hello world! azure"]}

        # flow evc can work
        flow_path = Path(f"{EAGER_FLOWS_DIR}/environment_variables_connection")
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.line_number": [0], "outputs.output": ["Hello world! azure"]}

    def test_run_with_deployment_overwrite(self, pf):
        run = pf.run(
            flow=f"{FLOWS_DIR}/python_tool_deployment_name",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            column_mapping={"key": "${data.key}"},
            connections={"print_env": {"deployment_name": "my_deployment_name", "model": "my_model"}},
        )
        run_dict = run._to_dict()
        assert "error" not in run_dict, run_dict["error"]
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {
            "inputs.key": ["API_BASE"],
            "inputs.line_number": [0],
            "outputs.output": [{"deployment_name": "my_deployment_name", "model": "my_model"}],
        }

        # TODO(3021931): this should fail.
        run = pf.run(
            flow=f"{FLOWS_DIR}/deployment_name_not_enabled",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            column_mapping={"env": "${data.key}"},
            connections={"print_env": {"deployment_name": "my_deployment_name", "model": "my_model"}},
        )
        run_dict = run._to_dict()
        assert "error" not in run_dict, run_dict["error"]

    def test_deployment_overwrite_failure(self, local_client, local_aoai_connection, pf):
        # deployment name not exist
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            connections={"classify_with_llm": {"deployment_name": "not_exist"}},
        )
        run_dict = run._to_dict()
        assert "error" in run_dict
        assert "The API deployment for this resource does not exist." in run_dict["error"]["message"]

        # deployment name not a param
        run = pf.run(
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            connections={"print_env": {"deployment_name": "not_exist"}},
        )
        run_dict = run._to_dict()
        assert "error" in run_dict
        assert "get_env_var() got an unexpected keyword argument" in run_dict["error"]["message"]

    def test_shadow_evc(self, pf):
        # run without env override will fail
        with pytest.raises(ConnectionNotFoundError):
            pf.run(
                flow=f"{FLOWS_DIR}/evc_connection_not_exist",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
            )
        # won't fail with connection not found
        run = pf.run(
            flow=f"{FLOWS_DIR}/evc_connection_not_exist",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            environment_variables={"API_BASE": "VAL"},
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.key": ["API_BASE"], "inputs.line_number": [0], "outputs.output": ["VAL"]}

    def test_shadow_evc_flex_flow(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/evc_connection_not_exist")

        # run without env override will fail
        with pytest.raises(ConnectionNotFoundError):
            pf.run(
                flow=flow_path,
                data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            )

        # won't fail in flex flow
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            environment_variables={"TEST": "VAL"},
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {"inputs.line_number": [0], "outputs.output": ["Hello world! VAL"]}

    def test_eager_flow_evc_override(self, pf):
        # resolve evc when used same name as flow's evc
        flow_path = Path(f"{EAGER_FLOWS_DIR}/print_environment_variables")
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/env_var_test.jsonl",
            environment_variables={"TEST": "${azure_open_ai_connection.api_type}"},
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict(), run._to_dict()["error"]
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {
            "inputs.key": ["TEST"],
            "inputs.line_number": [0],
            "outputs.output": ["Hello world! azure"],
        }

        # won't get connection & resolve when added new env var names
        flow_path = Path(f"{EAGER_FLOWS_DIR}/print_environment_variables")
        run = pf.run(
            flow=flow_path,
            data=f"{DATAS_DIR}/env_var_new_key.jsonl",
            environment_variables={"NEW_KEY": "${not_exist.api_type}"},
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict(), run._to_dict()["error"]
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {
            "inputs.key": ["NEW_KEY"],
            "inputs.line_number": [0],
            "outputs.output": ["Hello world! ${not_exist.api_type}"],
        }

    def test_run_with_non_provided_connection_override(self, pf, local_custom_connection):
        # override non-provided connection when submission
        run = pf.run(
            flow=f"{FLOWS_DIR}/connection_not_provided",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            column_mapping={"key": "${data.key}"},
            connections={"print_env": {"connection": "test_custom_connection"}},
        )
        run_dict = run._to_dict()
        assert "error" not in run_dict, run_dict["error"]
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {
            "inputs.key": ["API_BASE"],
            "inputs.line_number": [0],
            "outputs.output": [{"connection": "Custom", "key": "API_BASE"}],
        }

    def test_run_with_non_provided_connection_override_list_annotation(self, pf, local_custom_connection):
        # override non-provided connection when submission
        run = pf.run(
            flow=f"{FLOWS_DIR}/list_connection_not_provided",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            column_mapping={"key": "${data.key}"},
            connections={"print_env": {"connection": "test_custom_connection"}},
        )
        run_dict = run._to_dict()
        assert "error" not in run_dict, run_dict["error"]
        details = pf.get_details(run.name)
        # convert DataFrame to dict
        details_dict = details.to_dict(orient="list")
        assert details_dict == {
            "inputs.key": ["API_BASE"],
            "inputs.line_number": [0],
            "outputs.output": [{"connection": "Custom", "key": "API_BASE"}],
        }

    def test_run_with_init(self, pf):
        def assert_func(details_dict):
            return details_dict["outputs.func_input"] == [
                "func_input",
                "func_input",
                "func_input",
                "func_input",
            ] and details_dict["outputs.obj_input"] == ["val", "val", "val", "val"]

        def assert_metrics(metrics_dict):
            return metrics_dict == {"length": 4}

        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_callable_class")
        run = pf.run(
            flow=flow_path, data=f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl", init={"obj_input": "val"}
        )
        assert_batch_run_result(run, pf, assert_func)
        assert_run_metrics(run, pf, assert_metrics)

        run = load_run(
            source=f"{EAGER_FLOWS_DIR}/basic_callable_class/run.yaml",
        )
        run = pf.runs.create_or_update(run=run)
        assert_batch_run_result(run, pf, assert_func)
        assert_run_metrics(run, pf, assert_metrics)

    def test_run_with_init_class(self, pf):
        def assert_func(details_dict):
            return details_dict["outputs.func_input"] == [
                "func_input",
                "func_input",
                "func_input",
                "func_input",
            ] and details_dict["outputs.obj_input"] == ["val", "val", "val", "val"]

        with inject_sys_path(f"{EAGER_FLOWS_DIR}/basic_callable_class"):
            from simple_callable_class import MyFlow

            run = pf.run(
                flow=MyFlow,
                data=f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl",
                init={"obj_input": "val"},
                # set code folder to avoid snapshot too big
                code=f"{EAGER_FLOWS_DIR}/basic_callable_class",
            )

            assert_batch_run_result(run, pf, assert_func)

            run = pf.run(
                flow=MyFlow(obj_input="val"),
                data=f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl",
                # set code folder to avoid snapshot too big
                code=f"{EAGER_FLOWS_DIR}/basic_callable_class",
            )

            assert_batch_run_result(run, pf, assert_func)

    def test_model_config_in_init(self, pf):
        def assert_func(details_dict):
            keys_to_omit = [
                "inputs.line_number",
                "inputs.func_input",
                "outputs.func_input",
                "outputs.obj_id",
                "outputs.azure_open_ai_model_config_azure_endpoint",
            ]
            omitted_output = {k: v for k, v in details_dict.items() if k not in keys_to_omit}
            return omitted_output == {
                "outputs.azure_open_ai_model_config_deployment": ["my_deployment", "my_deployment"],
                "outputs.azure_open_ai_model_config_connection": ["(Failed)", "(Failed)"],
                "outputs.open_ai_model_config_model": ["my_model", "my_model"],
                "outputs.open_ai_model_config_base_url": ["fake_base_url", "fake_base_url"],
                "outputs.open_ai_model_config_connection": ["(Failed)", "(Failed)"],
            }

        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_model_config")

        # init with model config object
        config1 = AzureOpenAIModelConfiguration(azure_deployment="my_deployment", connection="azure_open_ai_connection")
        config2 = OpenAIModelConfiguration(model="my_model", base_url="fake_base_url")
        run = pf.run(
            flow=flow_path,
            data=f"{EAGER_FLOWS_DIR}/basic_model_config/inputs.jsonl",
            init={"azure_open_ai_model_config": config1, "open_ai_model_config": config2},
        )
        assert_batch_run_result(run, pf, assert_func)

        # init with model config dict
        config1 = dict(azure_deployment="my_deployment", connection="azure_open_ai_connection")
        config2 = dict(model="my_model", base_url="fake_base_url")
        run = pf.run(
            flow=flow_path,
            data=f"{EAGER_FLOWS_DIR}/basic_model_config/inputs.jsonl",
            init={"azure_open_ai_model_config": config1, "open_ai_model_config": config2},
        )
        assert_batch_run_result(run, pf, assert_func)

    def test_run_yaml_with_init_file(self, pf):
        def assert_func(details_dict):
            return details_dict["outputs.func_input"] == [
                "func_input",
                "func_input",
                "func_input",
                "func_input",
            ] and details_dict["outputs.obj_input"] == ["val", "val", "val", "val"]

        run = load_run(
            source=f"{EAGER_FLOWS_DIR}/basic_callable_class/run.yaml",
        )
        run = pf.runs.create_or_update(run=run)
        assert_batch_run_result(run, pf, assert_func)

    def test_flow_run_with_enriched_error_message(self, pf):
        config = AzureOpenAIModelConfiguration(
            connection="azure_open_ai_connection", azure_deployment="gpt-35-turbo-0125"
        )
        flow_path = Path(f"{EAGER_FLOWS_DIR}/stream_prompty")
        init_config = {"model_config": config}

        run = pf.run(
            flow=flow_path,
            data=f"{EAGER_FLOWS_DIR}/stream_prompty/inputs.jsonl",
            column_mapping={
                "question": "${data.question}",
                "chat_history": "${data.chat_history}",
            },
            init=init_config,
        )
        run_dict = run._to_dict()
        error = run_dict["error"]["additionalInfo"][0]["info"]["errors"][0]["error"]
        assert "Execution failure in 'ChatFlow.__call__" in error["message"]
        assert "raise Exception" in error["additionalInfo"][0]["info"]["traceback"]

    def test_run_with_yaml_default(self, pf):
        def assert_func(details_dict):
            return details_dict == {
                "inputs.func_input1": ["func_input"],
                "inputs.func_input2": ["default_func_input"],
                "inputs.line_number": [0],
                "outputs.output": ["default_obj_input_func_input_default_func_input"],
            }

        def assert_metrics(metrics_dict):
            return metrics_dict == {"length": 1}

        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_with_yaml_default")
        run = pf.run(
            flow=flow_path,
            data=f"{EAGER_FLOWS_DIR}/basic_with_yaml_default/inputs.jsonl",
            input_mapping={"func_input1": "${data.func_input1}"},
        )
        assert_batch_run_result(run, pf, assert_func)
        assert_run_metrics(run, pf, assert_metrics)

        run = load_run(
            source=f"{EAGER_FLOWS_DIR}/basic_with_yaml_default/run.yaml",
        )
        run = pf.runs.create_or_update(run=run)
        assert_batch_run_result(run, pf, assert_func)
        assert_run_metrics(run, pf, assert_metrics)

    def test_run_with_yaml_default_override(self, pf):
        def assert_func(details_dict):
            return details_dict == {
                "inputs.func_input1": ["func_input"],
                "inputs.func_input2": ["func_input"],
                "inputs.line_number": [0],
                "outputs.output": ["obj_input_func_input_func_input"],
            }

        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_with_yaml_default")

        run = pf.run(
            flow=flow_path,
            data=f"{EAGER_FLOWS_DIR}/basic_with_yaml_default/inputs_override.jsonl",
            column_mapping={"func_input1": "${data.func_input1}", "func_input2": "${data.func_input2}"},
            init={"obj_input": "obj_input"},
        )
        assert_batch_run_result(run, pf, assert_func)

    def test_visualize_different_runs(self, pf: PFClient) -> None:
        # prepare a DAG flow run, a flex flow run and a prompty run
        # DAG flow run
        dag_flow_run = pf.run(
            flow=Path(f"{FLOWS_DIR}/web_classification").absolute(),
            data=Path(f"{DATAS_DIR}/webClassification3.jsonl").absolute(),
            column_mapping={"name": "${data.url}"},
        )
        # flex flow run
        flex_flow_run = pf.run(
            flow=Path(f"{EAGER_FLOWS_DIR}/simple_with_yaml").absolute(),
            data=Path(f"{DATAS_DIR}/simple_eager_flow_data.jsonl").absolute(),
        )
        # prompty run
        prompty_run = pf.run(
            flow=Path(f"{TEST_ROOT / 'test_configs/prompty'}/prompty_example.prompty").absolute(),
            data=Path(f"{DATAS_DIR}/prompty_inputs.jsonl").absolute(),
        )

        with patch.object(pf.runs, "_visualize") as static_vis_func, patch.object(
            pf.runs, "_visualize_with_trace_ui"
        ) as trace_ui_vis_func:
            # visualize DAG flow run, will use legacy static visualize
            pf.visualize(runs=dag_flow_run)
            assert static_vis_func.call_count == 1 and trace_ui_vis_func.call_count == 0
            # visualize flex flow run, will use trace UI visualize
            pf.visualize(runs=flex_flow_run)
            assert static_vis_func.call_count == 1 and trace_ui_vis_func.call_count == 1
            # visualize prompty run, will use trace UI visualize
            pf.visualize(runs=prompty_run)
            assert static_vis_func.call_count == 1 and trace_ui_vis_func.call_count == 2
            # visualize both runs, will use trace UI visualize
            pf.visualize(runs=[dag_flow_run, flex_flow_run, prompty_run])
            assert static_vis_func.call_count == 1 and trace_ui_vis_func.call_count == 3

    def test_flex_flow_run_flow_type(self, pf: PFClient) -> None:
        run = pf.run(
            flow="entry:my_flow",
            code=f"{EAGER_FLOWS_DIR}/simple_without_yaml",
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
        )
        # BUG 3195705: uncomment below line after bug fixed, current value is "dag"
        # assert run._flow_type == FlowType.FLEX_FLOW
        assert pf.runs._get_run_flow_type(run) == FlowType.FLEX_FLOW

    def test_dump_snapshot_honor_ignore_file(self, pf: PFClient) -> None:
        run = pf.run(
            flow=f"{FLOWS_DIR}/print_env_var_with_aml_ignore",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
        )
        snapshot_folder = run._output_path / "snapshot"
        assert not (snapshot_folder / "ignore_a").exists()
        assert not (snapshot_folder / "ignore_b").exists()

    def test_installed_entry_without_snapshot(self, pf):
        run = pf.run(
            flow=_parse_otel_span_status_code,
            data=f"{DATAS_DIR}/simple_eager_flow_data_numbers.jsonl",
            column_mapping={"value": "${data.value}"},
        )
        snapshot_folder = run._output_path / "snapshot"
        # check snapshot folder will only contain flow.flex.yaml
        assert len(os.listdir(snapshot_folder)) == 1
        assert (snapshot_folder / "flow.flex.yaml").exists()


def assert_batch_run_result(run: Run, pf: PFClient, assert_func):
    assert run.status == "Completed"
    assert "error" not in run._to_dict(), run._to_dict()["error"]
    details = pf.get_details(run.name)
    # convert DataFrame to dict
    details_dict = details.to_dict(orient="list")
    assert assert_func(details_dict), details_dict


def assert_run_metrics(run: Run, pf: PFClient, assert_func):
    assert run.status == "Completed"
    assert "error" not in run._to_dict(), run._to_dict()["error"]
    metrics = pf.runs.get_metrics(run.name)
    assert assert_func(metrics), metrics
