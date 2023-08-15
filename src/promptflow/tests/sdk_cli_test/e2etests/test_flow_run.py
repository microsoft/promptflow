import os
import uuid
from pathlib import Path

import pandas as pd
import pytest

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow._sdk._constants import RunStatus
from promptflow._sdk._run_functions import create_yaml_run
from promptflow._sdk._utils import _get_additional_includes
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._flow import Flow
from promptflow._sdk.exceptions import InvalidFlowError, InvalidRunStatusError, RunNotFoundError
from promptflow._sdk.operations._run_submitter import SubmitterHelper
from promptflow.connections import AzureOpenAIConnection
from promptflow.executor.error_codes import InputNotFoundInInputsMapping

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
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
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used default variant config
        assert tuning_node["inputs"]["temperature"] == 0.3
        assert "default" in result.name

        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"
        # write to user_dir/.promptflow/.runs
        assert ".promptflow" in run.properties["output_path"]

    def test_basic_flow_with_variant(self, azure_open_ai_connection: AzureOpenAIConnection, local_client, pf) -> None:
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        assert "variant_0" in result.name

        # used variant_0 config
        assert tuning_node["inputs"]["temperature"] == 0.2
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_1}",
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        assert "variant_1" in result.name
        # used variant_1 config
        assert tuning_node["inputs"]["temperature"] == 0.3

    def test_run_bulk_error(self, pf):
        # path not exist
        with pytest.raises(FileNotFoundError) as e:
            pf.run(
                flow=f"{MODEL_ROOT}/not_exist",
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
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=f"{DATAS_DIR}/webClassification3.jsonl",
                column_mapping={"question": "${data.question}", "context": "${data.context}"},
                variant="v",
            )
        assert "Invalid variant format: v, variant should be in format of ${TUNING_NODE.VARIANT}" in str(e.value)

    def test_basic_evaluation(self, azure_open_ai_connection: AzureOpenAIConnection, local_client, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
        )
        assert local_client.runs.get(result.name).status == "Completed"

        eval_result = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=result.name,
            column_mapping={
                "groundtruth": "${data.answer}",
                "prediction": "${run.outputs.category}",
                # evaluation reference run.inputs
                "variant_id": "${data.variant_id}",
            },
        )
        assert local_client.runs.get(eval_result.name).status == "Completed"

    def test_flow_demo(self, azure_open_ai_connection, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        column_mapping = {
            "groundtruth": "data.answer",
            "prediction": "run.outputs.category",
            "variant_id": "data.variant_id",
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

        # TODO: compare metrics

    def test_submit_run_from_yaml(self, local_client, pf):
        run_id = str(uuid.uuid4())
        run = create_yaml_run(source=f"{RUNS_DIR}/sample_bulk_run.yaml", params_override=[{"name": run_id}])

        assert local_client.runs.get(run.name).status == "Completed"

        eval_run = create_yaml_run(
            source=f"{RUNS_DIR}/sample_eval_run.yaml",
            params_override=[{"run": run_id}],
        )
        assert local_client.runs.get(eval_run.name).status == "Completed"

    def test_run_with_connection(self, local_client, local_aoai_connection, pf):
        # remove connection file to test connection resolving
        os.environ.pop(PROMPTFLOW_CONNECTIONS)
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
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
        assert "Connection with name new_connection not found" in str(e.value)

    def test_run_with_connection_overwrite_non_exist(self, local_client, local_aoai_connection, pf):
        # overwrite non_exist connection
        with pytest.raises(Exception) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=f"{DATAS_DIR}/webClassification1.jsonl",
                connections={"classify_with_llm": {"connection": "Not_exist"}},
            )
        assert "Connection 'Not_exist' required for flow" in str(e)

    def test_run_reference_failed_run(self, pf):
        failed_run = pf.run(
            flow=f"{FLOWS_DIR}/failed_flow",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"text": "${data.url}"},
        )
        assert failed_run.status == "Failed"

        run_name = str(uuid.uuid4())
        with pytest.raises(ValueError) as e:
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

    def test_connection_overwrite_file(self, local_client, local_aoai_connection):
        run = create_yaml_run(
            source=f"{RUNS_DIR}/run_with_connections.yaml",
        )
        run = local_client.runs.get(name=run.name)
        assert run.status == "Completed"

    def test_resolve_connection(self, local_client, local_aoai_connection):
        flow = Flow.load(f"{FLOWS_DIR}/web_classification_no_variants")
        connections = SubmitterHelper.resolve_connections(flow)
        assert local_aoai_connection.name in connections

    def test_run_with_env_overwrite(self, local_client, local_aoai_connection):
        run = create_yaml_run(
            source=f"{RUNS_DIR}/run_with_env.yaml",
        )
        outputs = local_client.runs._get_outputs(run=run)
        assert "openai.azure.com" in outputs["output"][0]

    def test_pf_run_with_env_overwrite(self, local_client, local_aoai_connection, pf):
        run = pf.run(
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
        )
        outputs = local_client.runs._get_outputs(run=run)
        assert "openai.azure.com" in outputs["output"][0]

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
        assert run.display_name == display_name
        assert run.tags == tags

    def test_run_display_name(self, pf):
        run = pf.runs.create_or_update(
            run=Run(
                flow=Path(f"{FLOWS_DIR}/print_env_var"),
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
            )
        )
        assert run.display_name == run.name
        run = pf.runs.create_or_update(
            run=Run(
                flow=Path(f"{FLOWS_DIR}/print_env_var"),
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables={"API_BASE": "${azure_open_ai_connection.api_base}"},
                display_name="my_run",
            )
        )
        assert run.display_name == "my_run"

    def test_run_dump(self, azure_open_ai_connection: AzureOpenAIConnection, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        # in fact, `pf.run` will internally query the run from db in `RunSubmitter`
        # explicitly call ORM get here to emphasize the dump operatoin
        pf_client = pf
        pf_client.runs.get(run.name)

        # test list API here, so that we don't need to use @pytest.mark.last
        runs = pf_client.runs.list(max_results=1)
        assert len(runs) == 1

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
        assert 'Run status: "Failed"' in out
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

    def test_incomplete_run_visualize(self, azure_open_ai_connection: AzureOpenAIConnection, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path)
        # modify status in memory
        run._status = RunStatus.FAILED
        with pytest.raises(InvalidRunStatusError):
            pf.visualize(run)

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

    def test_input_mapping_parse_error(self, azure_open_ai_connection: AzureOpenAIConnection, pf):
        # input_mapping parse error won't create run
        name = str(uuid.uuid4())
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        with pytest.raises(InputNotFoundInInputsMapping):
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=data_path,
                column_mapping={"not_exist": "${data.url}"},
                name=name,
            )

        # run should not be created
        with pytest.raises(RunNotFoundError):
            pf.runs.get(name=name)

    def test_input_mapping_with_dict(self, azure_open_ai_connection: AzureOpenAIConnection, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        run = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_dict_input",
            data=data_path,
            column_mapping={"key": {"value": "1"}},
        )
        outputs = pf.runs._get_outputs(run=run)
        assert "dict" in outputs["output"][0]
